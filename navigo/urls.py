from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('package/<int:pk>/', views.package_detail, name='package_detail'),
    path('book/<int:pk>/', views.book_package, name='book_page'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),
    path('register/', views.register, name='register'),
    path('vendor/register/', views.vendor_register, name='vendor_register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile, name='profile'),
path('booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),  # Traveler cancel
    path('admin/booking/<int:pk>/cancel/', views.admin_cancel_booking, name='admin_cancel_booking'),  # Admin cancel
    path('vendor/', views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/package/create/', views.create_package, name='create_package'),
    path('edit-package/<int:package_id>/', views.edit_package, name='edit_package'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/package/<int:pk>/approve/', views.approve_package, name='approve_package'),
    path('admin/package/<int:pk>/unapprove/', views.unapprove_package, name='unapprove_package'),
    path('admin/package/<int:pk>/delete/', views.delete_package, name='delete_package'),
    path('admin/package/<int:pk>/update-expiry/', views.update_package_expiry, name='update_package_expiry'),
    path('admin/user/<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('admin/user/<int:user_id>/toggle-vendor/', views.toggle_vendor_status, name='toggle_vendor_status'),
    path('admin/booking/<int:pk>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('about/', views.about, name='about'),

]
