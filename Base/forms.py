# Base/forms.py
from django import forms
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from .models import Profile
from django.contrib.auth.forms import UserCreationForm
from Base.models import ROLE_CHOICES

class UserUpdateForm(forms.ModelForm):
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
        fields = ['first_name', 'last_name', 'email']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture']

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=ROLE_CHOICES, required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'role']

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