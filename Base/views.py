# Base/views.py
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.cache import cache
from .models import Product
from .models import Product, CATEGORY_CHOICES
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.views import PasswordResetView
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponseForbidden
from django.middleware.csrf import get_token
from django.urls import reverse_lazy
from .models import Profile
from .forms import SignUpForm
from django.contrib.auth import login
from .models import AuditLog, PCBuild, PCBuildItem, StockMovement
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Exists, OuterRef, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

# new imports
from .forms import UserUpdateForm, ProfileUpdateForm

def _normalized_text(value):
    return " ".join((value or '').split()).casefold()

def _querystring_without_page(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()

def _is_admin(user):
    profile = getattr(user, 'profile', None)
    return bool(user.is_authenticated and profile and profile.role == 'admin')

def _get_client_ip(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')

def _consume_rate_limit(scope, key, limit, window_seconds):
    cache_key = f"rate_limit:{scope}:{key}"
    attempts = cache.get(cache_key, 0)
    if attempts >= limit:
        return False

    if attempts == 0:
        cache.set(cache_key, 1, timeout=window_seconds)
    else:
        try:
            cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, attempts + 1, timeout=window_seconds)
    return True

def _clear_rate_limit(scope, key):
    cache.delete(f"rate_limit:{scope}:{key}")

def _create_audit_log(request, action, status, user=None, identifier='', metadata=None):
    AuditLog.objects.create(
        user=user,
        action=action,
        status=status,
        identifier=identifier or '',
        ip_address=_get_client_ip(request),
        metadata=metadata or {},
    )


def csrf_failure(request, reason=''):
    """
    Recover gracefully from stale/missing CSRF token on login-like pages.
    Instead of showing raw 403 in dev flows, redirect to a fresh GET so the
    browser receives a new CSRF cookie + token pair.
    """
    login_like_paths = {'/admin/login/', '/login/'}
    if request.method == 'POST' and request.path in login_like_paths:
        # Force creation/rotation of token on the next page load.
        get_token(request)
        return redirect(f"{request.path}?csrf=refresh")

    return HttpResponseForbidden("CSRF verification failed. Please refresh and try again.")

def admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, *args, **kwargs):
        if not _is_admin(request.user):
            messages.error(request, "Admin access required for this action.")
            return redirect('landing')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


class ForgotPasswordView(PasswordResetView):
    template_name = 'auth/forgot_password_form.html'
    email_template_name = 'auth/forgot_password_email.html'
    subject_template_name = 'auth/forgot_password_subject.txt'
    success_url = reverse_lazy('forgot_password_done')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST':
            email = (request.POST.get('email') or '').strip().casefold()
            ip_address = _get_client_ip(request)
            limit = int(getattr(settings, 'FORGOT_PASSWORD_RATE_LIMIT_ATTEMPTS', 3))
            window = int(getattr(settings, 'FORGOT_PASSWORD_RATE_LIMIT_WINDOW_SECONDS', 900))
            rate_key = f"{ip_address}:{email or 'blank'}"
            if not _consume_rate_limit('forgot_password', rate_key, limit, window):
                messages.error(request, "Too many reset requests. Please try again later.")
                _create_audit_log(
                    request,
                    action='forgot_password',
                    status='rate_limited',
                    identifier=email,
                    metadata={'reason': 'too_many_requests'},
                )
                return redirect('forgot_password')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        email = (form.cleaned_data.get('email') or '').strip().casefold()
        _create_audit_log(
            self.request,
            action='forgot_password',
            status='success',
            identifier=email,
        )
        return super().form_valid(form)

@login_required
def landing(request):
    products = Product.objects.filter(is_archived=False).order_by('-created_at')
    now = timezone.now()
    months_back = 6
    start_date = now - timedelta(days=30 * (months_back - 1))
    start_month = start_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_analytics = (
        PCBuild.objects.filter(status='checked_out', created_at__gte=start_month)
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(
            revenue=Sum('total_price'),
            builds=Count('id'),
        )
        .order_by('month')
    )

    monthly_map = {
        entry['month'].strftime('%b %Y'): {
            'revenue': float(entry['revenue'] or 0),
            'builds': int(entry['builds'] or 0),
        }
        for entry in monthly_analytics
    }

    chart_labels = []
    chart_revenue = []
    chart_builds = []
    for offset in range(months_back - 1, -1, -1):
        month_date = (now - timedelta(days=30 * offset)).replace(day=1)
        month_key = month_date.strftime('%b %Y')
        chart_labels.append(month_key)
        month_data = monthly_map.get(month_key, {'revenue': 0.0, 'builds': 0})
        chart_revenue.append(round(month_data['revenue'], 2))
        chart_builds.append(month_data['builds'])

    return render(request, 'design/landing.html', {
        'products': products,
        'sales_chart_labels_json': json.dumps(chart_labels),
        'sales_chart_revenue_json': json.dumps(chart_revenue),
        'sales_chart_build_count_json': json.dumps(chart_builds),
    })

@admin_required
def product(request):
    checkout_item_exists = PCBuildItem.objects.filter(product_id=OuterRef('pk'))
    products = Product.objects.annotate(has_checkout_history=Exists(checkout_item_exists))

    # GET search query
    search_query = request.GET.get('search', '')

    # GET category filter
    category_filter = request.GET.get('category', '')
    
    # GET price filters
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    
    # GET stock status filter
    stock_status = request.GET.get('stock_status', '')
    archive_status = request.GET.get('archive_status', 'active')
    
    # GET sort option
    sort_by = request.GET.get('sort', '-created_at')

    # APPLY SEARCH FILTER
    if search_query:
        products = products.filter(name__icontains=search_query)

    # APPLY CATEGORY FILTER
    if category_filter:
        products = products.filter(category=category_filter)
    
    # APPLY PRICE FILTERS
    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except (InvalidOperation, ValueError):
            pass
    
    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except (InvalidOperation, ValueError):
            pass
    
    # APPLY STOCK STATUS FILTER
    if stock_status == 'in_stock':
        products = products.filter(quantity__gt=0)
    elif stock_status == 'low_stock':
        products = products.filter(quantity__gt=0, quantity__lte=5)
    elif stock_status == 'out_of_stock':
        products = products.filter(quantity__lte=0)

    # APPLY ARCHIVE FILTER
    if archive_status == 'archived':
        products = products.filter(is_archived=True)
    elif archive_status == 'all':
        pass
    else:
        archive_status = 'active'
        products = products.filter(is_archived=False)
    
    # APPLY SORTING
    products = products.order_by(sort_by)
    paginator = Paginator(products, 10)
    products_page = paginator.get_page(request.GET.get('page'))
    querystring = _querystring_without_page(request)

    return render(request, 'design/product.html', {
        'products': products_page,
        'search_query': search_query,
        'category_filter': category_filter,
        'min_price': min_price,
        'max_price': max_price,
        'stock_status': stock_status,
        'archive_status': archive_status,
        'sort_by': sort_by,
        'querystring': querystring,
    })

@admin_required
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name', '')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity', 0)
        category = request.POST.get('category')

        if not name or not price:
            messages.error(request, "Product name and price are required.")
            return redirect('product')

        normalized_name = _normalized_text(name)
        normalized_description = _normalized_text(description)
        duplicate_exists = any(
            _normalized_text(product.name) == normalized_name and
            _normalized_text(product.description) == normalized_description
            for product in Product.objects.filter(category=category).only('name', 'description')
        )

        if duplicate_exists:
            messages.error(
                request,
                "A product with the same name, description, and category already exists.",
            )
            return redirect('product')

        try:
            product = Product(
                name=name,
                description=description,
                price=price,
                quantity=int(quantity) if quantity else 0,
                category=category
            )
            product.full_clean()
            product.save()
            messages.success(request, f"Product '{name}' added successfully!")
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
        except Exception as e:
            messages.error(request, f"Error adding product: {str(e)}")

        return redirect('product')

    return redirect('product')

@login_required
def category(request):
    products = Product.objects.filter(is_archived=False)
    search_query = request.GET.get('search', '')
    category_filter = request.GET.get('category', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    stock_status = request.GET.get('stock_status', '')
    sort_by = request.GET.get('sort', '-created_at')

    if search_query:
        products = products.filter(name__icontains=search_query)

    if category_filter:
        products = products.filter(category=category_filter)

    if min_price:
        try:
            products = products.filter(price__gte=Decimal(min_price))
        except (InvalidOperation, ValueError):
            pass

    if max_price:
        try:
            products = products.filter(price__lte=Decimal(max_price))
        except (InvalidOperation, ValueError):
            pass

    if stock_status == 'in_stock':
        products = products.filter(quantity__gt=0)
    elif stock_status == 'low_stock':
        products = products.filter(quantity__gt=0, quantity__lte=5)
    elif stock_status == 'out_of_stock':
        products = products.filter(quantity__lte=0)

    products = products.order_by(sort_by)
    paginator = Paginator(products, 10)
    products_page = paginator.get_page(request.GET.get('page'))
    querystring = _querystring_without_page(request)

    return render(request, 'design/masterlist.html', {
        'products': products_page,
        'search_query': search_query,
        'category_filter': category_filter,
        'min_price': min_price,
        'max_price': max_price,
        'stock_status': stock_status,
        'sort_by': sort_by,
        'querystring': querystring,
    })

@admin_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        name = request.POST.get('name', '')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity', 0)
        category = request.POST.get('category')

        if not name or not price:
            messages.error(request, "Product name and price are required.")
            return redirect('product')

        try:
            product.name = name
            product.description = description
            product.price = price
            product.quantity = int(quantity) if quantity else 0
            product.category = category
            product.full_clean()
            product.save()

            messages.success(request, f"Product '{name}' updated successfully!")
        except ValidationError as e:
            messages.error(request, "; ".join(e.messages))
        except Exception as e:
            messages.error(request, f"Error updating product: {str(e)}")

        return redirect('product')

    products = Product.objects.all().order_by('-created_at')
    return render(request, 'design/product.html', {
    'products': products,
    'editing_product': product,
    'category_filter': request.GET.get('category', '')
})

@admin_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    if request.method == 'POST':
        product_name = product.name
        try:
            product.delete()
            messages.success(request, f"Product '{product_name}' deleted successfully!")
        except ProtectedError as e:
            protected_models = {
                f"{obj._meta.app_label}.{obj._meta.model_name}"
                for obj in getattr(e, 'protected_objects', [])
            }
            # NOTE: keep deletion blocked to preserve inventory/audit trails.
            if any(model_name.endswith('stockmovement') for model_name in protected_models):
                messages.error(
                    request,
                    f"Cannot delete '{product_name}' because stock movement logs exist for this product.",
                )
            else:
                messages.error(
                    request,
                    f"Cannot delete '{product_name}' because it is referenced by checkout history.",
                )
        except Exception as e:
            messages.error(request, f"Error deleting product: {str(e)}")
        return redirect('product')

    return redirect('product')

@login_required
def pc_builder(request):
    prefill_build_items = request.session.pop('prefill_build_items', [])
    prefill_notes = request.session.pop('prefill_notes', [])
    prefill_cancel_url = request.session.pop('prefill_cancel_url', '')

    # Fetch products per category
    ram = Product.objects.filter(category='ram', is_archived=False)
    motherboard = Product.objects.filter(category='motherboard', is_archived=False)
    cpu = Product.objects.filter(category='cpu', is_archived=False)
    gpu = Product.objects.filter(category='gpu', is_archived=False)
    storage = Product.objects.filter(category='storage', is_archived=False)
    psu = Product.objects.filter(category='psu', is_archived=False)
    case = Product.objects.filter(category='case', is_archived=False)

    return render(request, 'design/pc_builder.html', {
        'ram': ram,
        'motherboard': motherboard,
        'cpu': cpu,
        'gpu': gpu,
        'storage': storage,
        'psu': psu,
        'case': case,
        'prefill_build_items_json': json.dumps(prefill_build_items),
        'prefill_notes': prefill_notes,
        'show_reorder_cancel': bool(prefill_build_items),
        'prefill_cancel_url': prefill_cancel_url,
    })


@login_required
def reorder_build(request, build_id):
    build_filters = {'id': build_id, 'status': 'checked_out'}
    if not _is_admin(request.user):
        build_filters['user'] = request.user
    build = get_object_or_404(PCBuild, **build_filters)
    build_items = build.items.select_related('product')
    history_view = request.GET.get('view', 'active')
    if history_view not in ('active', 'archived'):
        history_view = 'active'

    prefill_items = []
    notes = []

    for item in build_items:
        product = item.product
        available_qty = max(product.quantity, 0)
        if available_qty <= 0:
            notes.append(f"{product.name} is currently out of stock and was skipped.")
            continue

        safe_qty = min(item.quantity, available_qty)
        if safe_qty < item.quantity:
            notes.append(
                f"{product.name} quantity was adjusted from {item.quantity} to {safe_qty} (available stock)."
            )

        prefill_items.append({
            'product_id': product.id,
            'quantity': safe_qty,
        })

    if not prefill_items:
        messages.error(request, "No items from this build are currently available to reorder.")
        return redirect('checkout-history-detail', build_id=build.id)

    request.session['prefill_build_items'] = prefill_items
    request.session['prefill_notes'] = notes
    request.session['prefill_cancel_url'] = f"/pc-builder/history/?view={history_view}"
    return redirect('pc-builder')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('landing')

    form = AuthenticationForm()

    if request.method == 'POST':
        raw_username = (request.POST.get('username') or '').strip()
        user_model = get_user_model()
        matched_user = user_model.objects.filter(username__iexact=raw_username).only('username').first()
        canonical_username = matched_user.username if matched_user else raw_username
        username = canonical_username.casefold()
        ip_address = _get_client_ip(request)
        limit = int(getattr(settings, 'LOGIN_RATE_LIMIT_ATTEMPTS', 5))
        window = int(getattr(settings, 'LOGIN_RATE_LIMIT_WINDOW_SECONDS', 300))
        rate_key = f"{ip_address}:{username or 'blank'}"

        if not _consume_rate_limit('login', rate_key, limit, window):
            messages.error(request, "Too many login attempts. Please try again later.")
            _create_audit_log(
                request,
                action='login',
                status='rate_limited',
                identifier=username,
                metadata={'reason': 'too_many_attempts'},
            )
            return render(request, 'auth/login.html', {'form': AuthenticationForm(data=request.POST)})

        auth_payload = request.POST.copy()
        auth_payload['username'] = canonical_username
        form = AuthenticationForm(data=auth_payload)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            _clear_rate_limit('login', rate_key)
            _create_audit_log(
                request,
                action='login',
                status='success',
                user=user,
                identifier=user.username,
            )
            return redirect('landing')
        else:
            messages.error(request, "Invalid username or password.")
            _create_audit_log(
                request,
                action='login',
                status='failed',
                identifier=username,
            )

    return render(request, 'auth/login.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        _create_audit_log(
            request,
            action='logout',
            status='success',
            user=request.user,
            identifier=request.user.username,
        )
    logout(request)
    return redirect('login')

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = user.profile
            profile.role = 'staff'
            profile.save()

            messages.success(request, "Account created successfully!")
            login(request, user)
            return redirect('landing')
    else:
        form = SignUpForm()

    return render(request, 'auth/signup.html', {'form': form})   

# ----------------- NEW: Profile Settings View -----------------
@login_required
def profile_settings(request):
    # Ensure profile exists (signals should create it, but safe-check)
    if not hasattr(request.user, 'profile'):
        from .models import Profile
        Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, "Profile updated successfully.")
            return redirect('profile-settings')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form,
    }
    return render(request, 'profile/settings.html', context)

@login_required
@transaction.atomic
def checkout_pc_build(request):
    if request.method != 'POST':
        return redirect('pc-builder')

    raw_items = request.POST.get('build_items', '[]')
    try:
        selected_items = json.loads(raw_items)
    except json.JSONDecodeError:
        messages.error(request, "Invalid build data.")
        return redirect('pc-builder')

    if not isinstance(selected_items, list) or not selected_items:
        messages.error(request, "No items selected for this build.")
        return redirect('pc-builder')

    requested_quantities = {}
    for item in selected_items:
        if not isinstance(item, dict):
            messages.error(request, "Invalid build item format.")
            return redirect('pc-builder')

        product_id = item.get('product_id')
        quantity = item.get('quantity')
        try:
            product_id = int(product_id)
            quantity = int(quantity)
        except (TypeError, ValueError):
            messages.error(request, "Invalid product or quantity.")
            return redirect('pc-builder')

        if product_id <= 0 or quantity <= 0:
            messages.error(request, "Invalid product or quantity.")
            return redirect('pc-builder')

        requested_quantities[product_id] = requested_quantities.get(product_id, 0) + quantity

    build, _ = PCBuild.objects.get_or_create(
        user=request.user,
        status='draft'
    )

    products = Product.objects.select_for_update().filter(
        id__in=requested_quantities.keys(),
        is_archived=False,
    )
    products_map = {product.id: product for product in products}
    if len(products_map) != len(requested_quantities):
        messages.error(request, "One or more selected products do not exist.")
        return redirect('pc-builder')

    for product_id, quantity in requested_quantities.items():
        product = products_map[product_id]
        if quantity > product.quantity:
            messages.error(request, f"Not enough stock for {product.name}")
            return redirect('pc-builder')

    build.items.all().delete()

    build_items_to_create = []
    total = Decimal('0.00')
    for product_id, quantity in requested_quantities.items():
        product = products_map[product_id]
        price_at_time = product.price

        build_items_to_create.append(
            PCBuildItem(
                build=build,
                product=product,
                quantity=quantity,
                price_at_time=price_at_time,
            )
        )

        product.quantity -= quantity
        product.save(update_fields=['quantity'])

        try:
            total += price_at_time * quantity
        except (TypeError, InvalidOperation):
            messages.error(request, "Could not compute total price.")
            return redirect('pc-builder')

    PCBuildItem.objects.bulk_create(build_items_to_create)

    build.total_price = total
    build.status = 'checked_out'
    build.save()

    messages.success(request, "PC Build checked out successfully!")
    return redirect('landing')
@login_required
def checkout_history(request):
    """Display checkout history with analytics"""
    view_mode = request.GET.get('view', 'active')
    show_archived = view_mode == 'archived'

    # Get checked-out builds based on selected tab
    builds_qs = PCBuild.objects.filter(
        status='checked_out',
        is_archived=show_archived,
    ).annotate(item_count=Count('items')).order_by('-created_at')
    if not _is_admin(request.user):
        builds_qs = builds_qs.filter(user=request.user)
    paginator = Paginator(builds_qs, 10)
    builds_page = paginator.get_page(request.GET.get('page'))
    
    # Analytics calculations
    total_builds = builds_qs.count()
    
    # Calculate total revenue using Python instead of Django ORM
    total_revenue = Decimal('0.00')
    for build in builds_qs:
        total_revenue += build.total_price
    
    avg_order_value = total_revenue / total_builds if total_builds > 0 else Decimal('0.00')
    
    # Most popular item
    most_popular_item = None
    most_popular_count = 0
    if total_builds > 0:
        popular = PCBuildItem.objects.filter(build__in=builds_qs).values('product__name').annotate(
            count=Count('id')
        ).order_by('-count').first()
        if popular:
            most_popular_item = popular['product__name']
            most_popular_count = popular['count']
    
    total_listed_builds = total_builds
    for page_index, build in enumerate(builds_page, start=1):
        global_index = (builds_page.number - 1) * paginator.per_page + page_index
        build.display_number = total_listed_builds - global_index + 1

    context = {
        'builds': builds_page,
        'total_builds': total_builds,
        'total_revenue': float(total_revenue),
        'avg_order_value': float(avg_order_value),
        'most_popular_item': most_popular_item,
        'most_popular_count': most_popular_count,
        'show_archived': show_archived,
        'querystring': _querystring_without_page(request),
    }
    return render(request, 'design/checkout_history.html', context)

@login_required
def checkout_history_detail(request, build_id):
    """Display detailed view of a specific build"""
    build_filters = {'id': build_id}
    if not _is_admin(request.user):
        build_filters['user'] = request.user
    build = get_object_or_404(PCBuild, **build_filters)
    stock_movements = StockMovement.objects.filter(build=build).order_by('-created_at')
    history_view = request.GET.get('view')
    if history_view not in ('active', 'archived'):
        history_view = 'archived' if build.is_archived else 'active'
    
    # Calculate average item price
    item_count = build.items.count()
    avg_item_price = build.total_price / item_count if item_count > 0 else Decimal('0.00')
    
    return render(request, 'design/checkout_history_detail.html', {
        'build': build,
        'stock_movements': stock_movements,
        'avg_item_price': avg_item_price,
        'history_view': history_view,
    })


@admin_required
def archive_build(request, build_id):
    if request.method != 'POST':
        return redirect('checkout-history')

    next_view = request.POST.get('next_view', 'active')
    if next_view not in ('active', 'archived'):
        next_view = 'active'

    build = get_object_or_404(PCBuild, id=build_id, status='checked_out')
    if not build.is_archived:
        build.is_archived = True
        build.save(update_fields=['is_archived'])
        messages.success(request, f"Build #{build.id} archived.")

    return redirect(f"/pc-builder/history/?view={next_view}")


@admin_required
def restore_build(request, build_id):
    if request.method != 'POST':
        return redirect('checkout-history')

    next_view = request.POST.get('next_view', 'active')
    if next_view not in ('active', 'archived'):
        next_view = 'active'

    build = get_object_or_404(PCBuild, id=build_id, status='checked_out')
    if build.is_archived:
        build.is_archived = False
        build.save(update_fields=['is_archived'])
        messages.success(request, f"Build #{build.id} restored.")

    return redirect(f"/pc-builder/history/?view={next_view}")


@admin_required
def delete_build(request, build_id):
    if request.method != 'POST':
        return redirect('checkout-history')

    next_view = request.POST.get('next_view', 'archived')
    if next_view not in ('active', 'archived'):
        next_view = 'archived'

    confirm_delete = (request.POST.get('confirm_delete') or '').strip()
    build = get_object_or_404(PCBuild, id=build_id, status='checked_out')

    if not build.is_archived:
        messages.error(request, "Only archived builds can be deleted permanently.")
        _create_audit_log(
            request,
            action='delete_build',
            status='failed',
            user=request.user,
            identifier=str(build.id),
            metadata={'reason': 'build_not_archived'},
        )
        return redirect(f"/pc-builder/history/?view={next_view}")

    if confirm_delete != 'DELETE':
        messages.error(request, "Permanent delete cancelled. Type DELETE to confirm.")
        _create_audit_log(
            request,
            action='delete_build',
            status='failed',
            user=request.user,
            identifier=str(build.id),
            metadata={'reason': 'missing_confirmation'},
        )
        return redirect(f"/pc-builder/history/?view={next_view}")

    deleted_build_id = build.id
    deleted_username = build.user.username
    deleted_total = str(build.total_price)
    build.delete()

    _create_audit_log(
        request,
        action='delete_build',
        status='success',
        user=request.user,
        identifier=str(deleted_build_id),
        metadata={
            'target_user': deleted_username,
            'total_price': deleted_total,
        },
    )
    messages.success(request, f"Build #{deleted_build_id} deleted permanently.")
    return redirect(f"/pc-builder/history/?view={next_view}")


@admin_required
def bulk_manage_builds(request):
    if request.method != 'POST':
        return redirect('checkout-history')

    action = (request.POST.get('bulk_action') or '').strip()
    next_view = request.POST.get('next_view', 'active')
    if next_view not in ('active', 'archived'):
        next_view = 'active'

    raw_ids = request.POST.getlist('selected_build_ids')
    try:
        selected_ids = [int(value) for value in raw_ids]
    except (TypeError, ValueError):
        selected_ids = []

    if not selected_ids:
        messages.error(request, "No builds selected.")
        return redirect(f"/pc-builder/history/?view={next_view}")

    builds = PCBuild.objects.filter(id__in=selected_ids, status='checked_out')
    if not builds.exists():
        messages.error(request, "Selected builds are no longer available.")
        return redirect(f"/pc-builder/history/?view={next_view}")

    changed_count = 0

    if action == 'archive':
        for build in builds:
            if not build.is_archived:
                build.is_archived = True
                build.save(update_fields=['is_archived'])
                changed_count += 1
        messages.success(request, f"{changed_count} build(s) archived.")
        return redirect("/pc-builder/history/?view=active")

    if action == 'restore':
        for build in builds:
            if build.is_archived:
                build.is_archived = False
                build.save(update_fields=['is_archived'])
                changed_count += 1
        messages.success(request, f"{changed_count} build(s) restored.")
        return redirect("/pc-builder/history/?view=archived")

    if action == 'delete':
        confirm_delete = (request.POST.get('confirm_delete') or '').strip()
        if confirm_delete != 'DELETE':
            messages.error(request, "Bulk delete cancelled. Type DELETE to confirm.")
            return redirect("/pc-builder/history/?view=archived")

        for build in builds:
            if not build.is_archived:
                continue
            deleted_build_id = build.id
            deleted_username = build.user.username
            deleted_total = str(build.total_price)
            build.delete()
            changed_count += 1
            _create_audit_log(
                request,
                action='delete_build',
                status='success',
                user=request.user,
                identifier=str(deleted_build_id),
                metadata={
                    'target_user': deleted_username,
                    'total_price': deleted_total,
                    'bulk': True,
                },
            )

        messages.success(request, f"{changed_count} build(s) deleted permanently.")
        return redirect("/pc-builder/history/?view=archived")

    messages.error(request, "Invalid bulk action.")
    return redirect(f"/pc-builder/history/?view={next_view}")


@admin_required
def archive_product(request, product_id):
    if request.method != 'POST':
        return redirect('product')

    product = get_object_or_404(Product, id=product_id)
    if not product.is_archived:
        product.is_archived = True
        product.save(update_fields=['is_archived'])
        messages.success(request, f"Product '{product.name}' archived.")
    return redirect('product')


@admin_required
def restore_product(request, product_id):
    if request.method != 'POST':
        return redirect('product')

    product = get_object_or_404(Product, id=product_id)
    if product.is_archived:
        product.is_archived = False
        product.save(update_fields=['is_archived'])
        messages.success(request, f"Product '{product.name}' restored.")
    return redirect('product')


@admin_required
def bulk_manage_products(request):
    if request.method != 'POST':
        return redirect('product')

    action = (request.POST.get('bulk_action') or '').strip()
    next_querystring = (request.POST.get('next_querystring') or '').strip()
    redirect_url = '/product/'
    if next_querystring:
        redirect_url = f"{redirect_url}?{next_querystring}"

    raw_ids = request.POST.getlist('selected_product_ids')
    try:
        selected_ids = [int(value) for value in raw_ids]
    except (TypeError, ValueError):
        selected_ids = []

    if not selected_ids:
        messages.error(request, "No products selected.")
        return redirect(redirect_url)

    products_qs = Product.objects.filter(id__in=selected_ids)
    if not products_qs.exists():
        messages.error(request, "Selected products are no longer available.")
        return redirect(redirect_url)

    changed_count = 0
    blocked_count = 0

    if action == 'archive':
        for product in products_qs:
            if not product.is_archived:
                product.is_archived = True
                product.save(update_fields=['is_archived'])
                changed_count += 1
        messages.success(request, f"{changed_count} product(s) archived.")
        return redirect(redirect_url)

    if action == 'restore':
        for product in products_qs:
            if product.is_archived:
                product.is_archived = False
                product.save(update_fields=['is_archived'])
                changed_count += 1
        messages.success(request, f"{changed_count} product(s) restored.")
        return redirect(redirect_url)

    if action == 'delete':
        confirm_delete = (request.POST.get('confirm_delete') or '').strip()
        if confirm_delete != 'DELETE':
            messages.error(request, "Bulk delete cancelled. Type DELETE to confirm.")
            return redirect(redirect_url)

        for product in products_qs:
            try:
                product.delete()
                changed_count += 1
            except ProtectedError:
                blocked_count += 1

        if changed_count:
            messages.success(request, f"{changed_count} product(s) deleted permanently.")
        if blocked_count:
            messages.error(
                request,
                f"{blocked_count} product(s) could not be deleted because they have related checkout/stock records.",
            )
        return redirect(redirect_url)

    messages.error(request, "Invalid bulk action.")
    return redirect(redirect_url)
