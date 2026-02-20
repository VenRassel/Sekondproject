# Base/views.py
import json
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Product
from .models import Product, CATEGORY_CHOICES
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required
from .models import Profile
from .forms import SignUpForm
from django.contrib.auth import login
from .models import PCBuild, PCBuildItem, StockMovement
from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import redirect, get_object_or_404
from django.utils import timezone

# new imports
from .forms import UserUpdateForm, ProfileUpdateForm

@login_required
def landing(request):
    products = Product.objects.all().order_by('-created_at')
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

@login_required
def product(request):
    products = Product.objects.all()

    # GET search query
    search_query = request.GET.get('search', '')

    # GET category filter
    category_filter = request.GET.get('category', '')
    
    # GET price filters
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    
    # GET stock status filter
    stock_status = request.GET.get('stock_status', '')
    
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
    
    # APPLY SORTING
    products = products.order_by(sort_by)

    return render(request, 'design/product.html', {
        'products': products,
        'search_query': search_query,
        'category_filter': category_filter,
        'min_price': min_price,
        'max_price': max_price,
        'stock_status': stock_status,
        'sort_by': sort_by,
    })

@login_required
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity', 0)
        category = request.POST.get('category')

        if not name or not price:
            messages.error(request, "Product name and price are required.")
            return redirect('product')

        try:
            Product.objects.create(
                name=name,
                description=description,
                price=price,
                quantity=int(quantity) if quantity else 0,
                category=category
            )
            messages.success(request, f"Product '{name}' added successfully!")
        except Exception as e:
            messages.error(request, f"Error adding product: {str(e)}")

        return redirect('product')

    return redirect('product')

@login_required
def category(request):
    category_filter = request.GET.get('category', '')

    products = Product.objects.all().order_by('-created_at')

    # APPLY CATEGORY FILTER
    if category_filter:
        products = products.filter(category=category_filter)

    return render(request, 'design/masterlist.html', {
        'products': products,
        'category_filter': category_filter
    })

@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    category_filter = request.GET.get('category', '')

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity', 0)
        category = request.POST.get('category')

        if not name or not price:
            messages.error(request, "Product name and price are required.")
            return redirect('category')

        try:
            product.name = name
            product.description = description
            product.price = price
            product.quantity = int(quantity) if quantity else 0
            product.category = category
            product.save()

            messages.success(request, f"Product '{name}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating product: {str(e)}")

        return redirect(f'/category/?category={category_filter}')

    products = Product.objects.all().order_by('-created_at')
    return render(request, 'design/product.html', {
    'products': products,
    'editing_product': product,
    'category_filter': request.GET.get('category', '')
})

@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    category_filter = request.GET.get('category', '')

    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f"Product '{product_name}' deleted successfully!")
        return redirect(f'/category/?category={category_filter}')

    return redirect('category')

@login_required
def pc_builder(request):
    prefill_build_items = request.session.pop('prefill_build_items', [])
    prefill_notes = request.session.pop('prefill_notes', [])
    prefill_cancel_url = request.session.pop('prefill_cancel_url', '')

    # Fetch products per category
    ram = Product.objects.filter(category='ram')
    motherboard = Product.objects.filter(category='motherboard')
    cpu = Product.objects.filter(category='cpu')
    gpu = Product.objects.filter(category='gpu')
    storage = Product.objects.filter(category='storage')
    psu = Product.objects.filter(category='psu')
    case = Product.objects.filter(category='case')

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
    build = get_object_or_404(PCBuild, id=build_id, status='checked_out')
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
        form = AuthenticationForm(data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('landing')
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, 'auth/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            role = form.cleaned_data['role']

            # No more duplicate Profile creation
            profile = user.profile
            profile.role = role
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

    products = Product.objects.select_for_update().filter(id__in=requested_quantities.keys())
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
    ).order_by('-created_at')
    builds = list(builds_qs)
    
    # Add item_count to each build for display
    total_listed_builds = len(builds)
    for index, build in enumerate(builds, start=1):
        build.display_number = total_listed_builds - index + 1
        build.item_count = build.items.count()
    
    # Analytics calculations
    from django.db.models import Sum, Count
    
    total_builds = builds_qs.count()
    
    # Calculate total revenue using Python instead of Django ORM
    total_revenue = Decimal('0.00')
    for build in builds:
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
    
    context = {
        'builds': builds,
        'total_builds': total_builds,
        'total_revenue': float(total_revenue),
        'avg_order_value': float(avg_order_value),
        'most_popular_item': most_popular_item,
        'most_popular_count': most_popular_count,
        'show_archived': show_archived,
    }
    import sys
    # Debug prints so you can see values when the page is requested
    print(f"DEBUG checkout_history -> total_builds={total_builds}, total_revenue={total_revenue}, avg_order_value={avg_order_value}", file=sys.stderr)

    return render(request, 'design/checkout_history.html', context)

@login_required
def checkout_history_detail(request, build_id):
    """Display detailed view of a specific build"""
    build = get_object_or_404(PCBuild, id=build_id)
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


@login_required
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


@login_required
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
