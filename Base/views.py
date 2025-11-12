from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Product

def landing(request):
    return render(request, 'design/landing.html')

def product(request):
    products = Product.objects.all()
    return render(request, 'design/product.html', {'products': products})

def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity', 0)
        
        if not name or not price:
            messages.error(request, "Product name and price are required.")
            return redirect('product')
        
        try:
            Product.objects.create(
                name=name,
                description=description,
                price=price,
                quantity=int(quantity) if quantity else 0
            )
            messages.success(request, f"Product '{name}' added successfully!")
        except Exception as e:
            messages.error(request, f"Error adding product: {str(e)}")
        
        return redirect('product')
    
    return redirect('product')

def edit_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description', '')
        price = request.POST.get('price')
        quantity = request.POST.get('quantity', 0)
        
        if not name or not price:
            messages.error(request, "Product name and price are required.")
            return redirect('product')
        
        try:
            product.name = name
            product.description = description
            product.price = price
            product.quantity = int(quantity) if quantity else 0
            product.save()
            messages.success(request, f"Product '{name}' updated successfully!")
        except Exception as e:
            messages.error(request, f"Error updating product: {str(e)}")
        
        return redirect('product')
    
    products = Product.objects.all()
    return render(request, 'design/product.html', {
        'products': products,
        'editing_product': product
    })

def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.method == 'POST':
        product_name = product.name
        product.delete()
        messages.success(request, f"Product '{product_name}' deleted successfully!")
        return redirect('product')
    
    return redirect('product')

