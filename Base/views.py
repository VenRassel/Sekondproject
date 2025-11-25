# Base/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Product
from .models import Product, CATEGORY_CHOICES
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.decorators import login_required

# new imports
from .forms import UserUpdateForm, ProfileUpdateForm

@login_required
def landing(request):
    products = Product.objects.all()
    return render(request, 'design/landing.html', {'products': products})

@login_required
def product(request):
    products = Product.objects.all()

    # GET search query
    search_query = request.GET.get('search', '')

    # GET category filter
    category_filter = request.GET.get('category', '')

    # APPLY SEARCH FILTER
    if search_query:
        products = products.filter(name__icontains = search_query)

    # APPLY CATEGORY FILTER
    if category_filter:
        products = products.filter(category = category_filter)

    return render(request, 'design/product.html', {
        'products': products,
        'search_query': search_query,
        'category_filter': category_filter,
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

    products = Product.objects.all()

    # APPLY CATEGORY FILTER
    if category_filter:
        products = products.filter(category=category_filter)

    return render(request, 'design/category.html', {
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

    products = Product.objects.all()
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
    })

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
    if request.user.is_authenticated:
        return redirect('landing')

    form = UserCreationForm()

    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('landing')
        else:
            messages.error(request, "Please correct the errors below.")

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
