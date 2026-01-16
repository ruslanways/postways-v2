from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm, UsernameField, PasswordResetForm, SetPasswordForm
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _
from .models import CustomUser, Post

class CustomUserCreationForm(UserCreationForm):

    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", 'class': "form-control"}),
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", 'class': "form-control"}),
        strip=False,
    )
    email = forms.EmailField(
        label="Email",
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", 'class': "form-control"}),
    )

    agree = forms.BooleanField(
                            label='Agree',
                            required = True,
                            disabled = False,
                            widget=forms.widgets.CheckboxInput(
                                attrs={'class': 'checkbox-inline'}),
                                help_text = "I allow to use Cookies on that web-site",
                                error_messages ={'required':'Please check the box'}
                            )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'agree')
        widgets = {
            'username': forms.TextInput(attrs={'class':'form-control'}),
            'agree': forms.CheckboxInput(attrs={'class':'form-control'}),
        }


class CustomAuthenticationForm(AuthenticationForm):

    username = UsernameField(widget=forms.TextInput(attrs={"autofocus": True, 'class':'form-control'}))
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password", 'class':'form-control'}),
    )

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email", 'class':'form-control'}),
    )


class CutomSetPasswordForm(SetPasswordForm):

    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", 'class':'form-control'}),
        strip=False,
        help_text=password_validation.password_validators_help_text_html(),
    )
    new_password2 = forms.CharField(
        label=_("New password confirmation"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password", 'class':'form-control'}),
    )


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = CustomUser
        fields = ('username', 'email')


class AddPostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = 'title', 'content', 'image', 'published'
        widgets = {
            'title': forms.TextInput(attrs={'class':'form-control'}),
            'content': forms.Textarea(attrs={'class':'form-control'}),
            'image': forms.FileInput(attrs={'class':'form-control'}),
            'published': forms.CheckboxInput(attrs={'class':'form-check-input'}),
        }
        labels = {
            'published': 'Publish'
        }


class UpdatePostForm(AddPostForm):

    class Meta(AddPostForm.Meta):
        help_texts = {
            'image': _("if you don't wish to change the image - just left it unattached here"),
        }
