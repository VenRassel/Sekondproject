# Base/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Profile
from django.contrib.auth.forms import UserCreationForm

class UserUpdateForm(forms.ModelForm):
    username = forms.CharField(
        required=True,
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Enter username'})
    )
    first_name = forms.CharField(
        required=False, 
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'Enter first name'})
    )
    last_name = forms.CharField(
        required=False, 
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'Enter last name'})
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'placeholder': 'Enter email address'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        duplicate_qs = User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk)
        if duplicate_qs.exists():
            raise forms.ValidationError("This username is already taken.")
        return username

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture']

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email

class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'autofocus': True,
            'placeholder': 'Enter your email'
        })
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter your password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            # Use filter().first() instead of get() to handle multiple users with same email
            users = User.objects.filter(email=email)
            if not users.exists():
                raise forms.ValidationError("Invalid email or password.")
            
            # Try to authenticate with each user that has this email
            authenticated_user = None
            for user in users:
                authenticated_user = authenticate(username=user.username, password=password)
                if authenticated_user:
                    break
            
            if authenticated_user is None:
                raise forms.ValidationError("Invalid email or password.")
            
            cleaned_data['user'] = authenticated_user
        
        return cleaned_data
