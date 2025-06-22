from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Package, Booking, PackageImage, UserProfile
from .forms import PackageForm, ProfileForm, BookingForm
from django.contrib.auth.forms import UserCreationForm
from django.conf import settings
from datetime import date
import razorpay
from django.contrib.auth.models import Group, User
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import hmac
import hashlib
import logging
from datetime import datetime
from django.contrib.auth.decorators import user_passes_test
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal  # Import Decimal for calculations
from django.db.models import Sum, Count, Q


logger = logging.getLogger(__name__)

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def home(request):
    packages = Package.objects.filter(is_approved=True, expiry_date__gte=date.today())
    top_packages = packages.order_by('-price')[:3]
    budget_packages = packages.order_by('price')[:3]
    return render(request, 'home.html', {
        'packages': packages,
        'top_packages': top_packages,
        'budget_packages': budget_packages,
        'testimonials': []
    })


def package_detail(request, pk):
    package = get_object_or_404(Package, pk=pk, is_approved=True)
    return render(request, 'package_detail.html', {'package': package})


@login_required
def book_package(request, pk):
    package = get_object_or_404(Package, pk=pk, is_approved=True)
    form = BookingForm(request.POST or None, package=package)  # Pass package to form

    if request.method == 'POST' and form.is_valid():
        try:
            number_of_persons = form.cleaned_data['number_of_persons']
            travel_date = form.cleaned_data['travel_date']  # Get travel_date from form

            # Calculate financial details using Decimal
            subtotal = package.price * number_of_persons
            discount = subtotal * Decimal('0.10') if number_of_persons >= 3 else Decimal('0.00')
            taxable_amount = subtotal - discount
            gst_amount = taxable_amount * Decimal('0.10')  # 10% GST
            platform_charge = Decimal('199.00')  # ₹199 platform charge
            total_amount = taxable_amount + gst_amount + platform_charge

            # Create Razorpay order
            order_amount = int(total_amount * 100)  # Convert to paise for Razorpay
            order_data = {
                'amount': order_amount,
                'currency': 'INR',
                'payment_capture': '1'
            }
            order = razorpay_client.order.create(data=order_data)
            logger.info(f"Created Razorpay order: {order['id']} for package {pk}")

            # Save booking with financial details
            booking = Booking.objects.create(
                user=request.user,
                package=package,
                payment_status='Pending',
                order_id=order['id'],
                number_of_persons=number_of_persons,
                travel_date=travel_date,
                subtotal=subtotal,
                discount=discount,
                gst_amount=gst_amount,
                platform_charge=platform_charge,
                total_amount=total_amount
            )

            return render(request, 'booking.html', {
                'package': package,
                'order_id': order['id'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount': order_amount,
                'booking_id': booking.id,
                'form': form,
                'total_amount': total_amount,  # In INR
                'number_of_persons': number_of_persons,
                'subtotal': subtotal,
                'discount': discount,
                'gst_amount': gst_amount,
                'platform_charge': platform_charge
            })
        except Exception as e:
            logger.error(f"Order creation failed for package {pk}: {str(e)}")
            messages.error(request, f'Payment initiation failed: {str(e)}')

    return render(request, 'booking.html', {
        'package': package,
        'form': form
    })


@csrf_exempt
def verify_payment(request):
    logger.info("verify_payment called")
    if request.method == 'POST':
        try:
            data = request.POST
            logger.debug(f"Received POST data: {data}")
            razorpay_payment_id = data.get('razorpay_payment_id')
            razorpay_order_id = data.get('razorpay_order_id')
            razorpay_signature = data.get('razorpay_signature')

            if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
                logger.error("Missing required Razorpay parameters")
                return JsonResponse({'status': 'error', 'message': 'Missing payment parameters'}, status=400)

            generated_signature = hmac.new(
                bytes(settings.RAZORPAY_KEY_SECRET, 'utf-8'),
                bytes(f"{razorpay_order_id}|{razorpay_payment_id}", 'utf-8'),
                hashlib.sha256
            ).hexdigest()

            logger.debug(f"Generated signature: {generated_signature}, Received signature: {razorpay_signature}")
            if generated_signature == razorpay_signature:
                booking = Booking.objects.get(order_id=razorpay_order_id)
                booking.payment_status = 'Completed'
                booking.status = 'Confirmed'
                booking.razorpay_payment_id = razorpay_payment_id
                booking.save()
                logger.info(f"Booking {booking.id} updated to Confirmed/Completed")
                return JsonResponse({'status': 'success', 'message': 'Payment verified successfully'})
            else:
                logger.error("Invalid payment signature")
                return JsonResponse({'status': 'error', 'message': 'Invalid payment signature'}, status=400)
        except Booking.DoesNotExist:
            logger.error(f"Booking not found for order_id: {razorpay_order_id}")
            return JsonResponse({'status': 'error', 'message': 'Booking not found'}, status=404)
        except Exception as e:
            logger.error(f"Payment verification error: {str(e)}")
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    logger.error("Invalid request method")
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. Please login.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})


def vendor_register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            vendor_group = Group.objects.get(name='Vendors')
            user.groups.add(vendor_group)
            messages.success(request, 'Vendor registration successful. Please login.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'vendor_register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.POST.get('next', request.GET.get('next', 'home'))
            if next_url in ['/accounts/login/', '/accounts/logout/']:
                next_url = 'home'
            return redirect(next_url)
        messages.error(request, 'Invalid credentials.')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
def profile(request):
    user = request.user
    try:
        user_profile = user.userprofile
    except UserProfile.DoesNotExist:
        user_profile = UserProfile(user=user)
        user_profile.save()

    vendor_packages = []
    vendor_bookings = []
    bookings = Booking.objects.filter(user=user)  # Always fetch personal bookings

    if user.groups.filter(name='Vendors').exists():
        vendor_packages = Package.objects.filter(vendor=user)
        vendor_bookings = Booking.objects.filter(package__vendor=user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            form = ProfileForm(request.POST, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('profile')
            else:
                messages.error(request, 'Please correct the errors below.')
        elif 'update_image' in request.POST:
            form = ProfileForm(request.POST, request.FILES, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, 'Profile image updated successfully.')
                return redirect('profile')
            else:
                messages.error(request, 'Error updating profile image.')
    else:
        form = ProfileForm(instance=user)

    context = {
        'user': user,
        'vendor_packages': vendor_packages,
        'vendor_bookings': vendor_bookings,
        'bookings': bookings,
        'form': form,
    }
    return render(request, 'profile.html', context)


def vendor_check(user):
    return user.groups.filter(name='Vendors').exists()


@user_passes_test(vendor_check)
@login_required
def vendor_dashboard(request):
    if not request.user.groups.filter(name='Vendors').exists():
        return redirect('home')
    packages = Package.objects.filter(vendor=request.user)
    bookings = Booking.objects.filter(package__vendor=request.user)
    return render(request, 'vendor_dashboard.html', {'packages': packages, 'bookings': bookings})


@login_required
def create_package(request):
    if not request.user.groups.filter(name='Vendors').exists():
        return redirect('home')
    if request.method == 'POST':
        form = PackageForm(request.POST, request.FILES)
        if form.is_valid():
            package = form.save(commit=False)
            package.vendor = request.user
            package.save()
            # Handle multiple image uploads
            images = request.FILES.getlist('images')
            for image in images:
                PackageImage.objects.create(package=package, image=image)
            messages.success(request, 'Package created. Awaiting admin approval.')
            return redirect('vendor_dashboard')
    else:
        form = PackageForm()
    return render(request, 'vendor_package_form.html', {'form': form})


@login_required
def edit_package(request, package_id):
    if not request.user.groups.filter(name='Vendors').exists():
        return redirect('home')
    package = get_object_or_404(Package, id=package_id, vendor=request.user)
    if request.method == 'POST':
        form = PackageForm(request.POST, request.FILES, instance=package)
        if form.is_valid():
            package = form.save(commit=False)
            package.save()
            # Handle new image uploads
            images = request.FILES.getlist('images')
            if images:
                for image in images:
                    PackageImage.objects.create(package=package, image=image)
            messages.success(request, 'Package updated successfully.')
            return redirect('vendor_dashboard')
    else:
        form = PackageForm(instance=package)
    return render(request, 'vendor_package_form.html', {'form': form, 'package': package})





@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')

    # Get base querysets
    packages = Package.objects.all()
    bookings = Booking.objects.all()
    users = User.objects.all()

    # Calculate revenue metrics
    total_revenue = bookings.aggregate(total=Sum('total_amount'))['total'] or 0
    paid_revenue = bookings.filter(payment_status='Paid').aggregate(total=Sum('total_amount'))['total'] or 0

    # Time-based metrics
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)

    monthly_revenue = bookings.filter(
        booking_date__gte=last_30_days
    ).aggregate(total=Sum('total_amount'))['total'] or 0

    # Count metrics
    active_packages = packages.filter(is_approved=True).count()
    pending_packages = packages.filter(is_approved=False).count()
    confirmed_bookings = bookings.filter(status='Confirmed').count()

    # User metrics
    total_users = users.count()
    vendors = users.filter(groups__name='Vendors').count()
    customers = total_users - vendors  # Assuming all non-vendors are customers

    context = {
        'packages': packages,
        'bookings': bookings,
        'users': users,

        # Revenue metrics
        'revenue': total_revenue,
        'paid_revenue': paid_revenue,
        'monthly_revenue': monthly_revenue,

        # Count metrics
        'active_packages': active_packages,
        'pending_packages': pending_packages,
        'confirmed_bookings': confirmed_bookings,

        # User metrics
        'total_users': total_users,
        'vendors': vendors,
        'customers': customers,
    }

    return render(request, 'admin_dashboard.html', context)


@login_required
def approve_package(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    package = get_object_or_404(Package, pk=pk)
    package.is_approved = True
    package.save()
    messages.success(request, 'Package approved.')
    return redirect('admin_dashboard')


@login_required
def unapprove_package(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    package = get_object_or_404(Package, pk=pk)
    package.is_approved = False
    package.save()
    messages.success(request, 'Package unapproved.')
    return redirect('admin_dashboard')


@login_required
def delete_package(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    package = get_object_or_404(Package, pk=pk)
    package.delete()
    messages.success(request, 'Package deleted.')
    return redirect('admin_dashboard')


@login_required
def update_package_expiry(request, pk):
    if not request.user.is_staff:
        return redirect('home')
    package = get_object_or_404(Package, pk=pk)
    if request.method == 'POST':
        expiry_date_str = request.POST.get('expiry_date')
        try:
            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
            if expiry_date < date.today():
                messages.error(request, 'Expiry date cannot be in the past.')
            else:
                package.expiry_date = expiry_date
                package.save()
                messages.success(request, 'Package expiry updated.')
        except ValueError:
            messages.error(request, 'Invalid date format.')
        return redirect('admin_dashboard')
    return render(request, 'update_expiry.html', {'package': package})


@login_required
def delete_user(request, user_id):
    if not request.user.is_staff:
        return redirect('home')
    user = get_object_or_404(User, id=user_id)
    if user.is_staff:
        messages.error(request, 'Cannot delete staff users.')
    else:
        user.delete()
        messages.success(request, 'User deleted.')
    return redirect('admin_dashboard')


@login_required
def toggle_vendor_status(request, user_id):
    if not request.user.is_staff:
        return redirect('home')
    user = get_object_or_404(User, id=user_id)
    vendor_group = Group.objects.get(name='Vendors')
    if user.groups.filter(name='Vendors').exists():
        user.groups.remove(vendor_group)
        messages.success(request, f'{user.username} removed from Vendors group.')
    else:
        user.groups.add(vendor_group)
        messages.success(request, f'{user.username} added to Vendors group.')
    return redirect('admin_dashboard')


@login_required
def admin_cancel_booking(request, pk):
    logger.debug(f"Admin cancel_booking called with pk={pk}")
    if not request.user.is_staff:
        logger.warning(f"Non-staff user {request.user.username} attempted to access admin_cancel_booking")
        return redirect('home')
    booking = get_object_or_404(Booking, pk=pk)
    logger.debug(f"Found booking {booking.id} with status {booking.status}")
    if booking.status == 'Confirmed':
        booking.status = 'Cancelled'
        booking.save()
        logger.info(f"Booking {booking.id} cancelled by admin {request.user.username}")
        messages.success(request, 'Booking cancelled successfully.')
    else:
        logger.warning(f"Booking {booking.id} cannot be cancelled; current status: {booking.status}")
        messages.error(request, 'Only confirmed bookings can be cancelled.')
    return redirect('admin_dashboard')


@login_required
def cancel_booking(request, booking_id):
    logger.debug(f"Traveler cancel_booking called with booking_id={booking_id}")
    if request.user.is_staff:
        logger.warning(f"Staff user {request.user.username} attempted to access cancel_booking")
        return redirect('home')
    try:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
        logger.debug(
            f"Found booking {booking.id} with status {booking.status}, payment_status={booking.payment_status}")
        if booking.status == 'Cancelled':
            logger.warning(f"Booking {booking.id} is already cancelled")
            messages.error(request, 'Booking is already cancelled.')
        elif booking.travel_date and booking.travel_date < timezone.now().date() + timedelta(days=2):
            logger.warning(f"Booking {booking.id} cannot be cancelled; travel date {booking.travel_date} is too close")
            messages.error(request, 'Cannot cancel booking within 48 hours of travel date.')
        elif booking.payment_status == 'Completed':
            logger.warning(f"Booking {booking.id} cannot be cancelled; payment completed")
            messages.error(request, 'Cannot cancel paid bookings. Contact support for a refund.')
        else:
            booking.status = 'Cancelled'
            booking.save()
            logger.info(f"Booking {booking.id} cancelled by user {request.user.username}")
            messages.success(request, 'Booking cancelled successfully.')
    except Booking.DoesNotExist:
        logger.error(f"Booking {booking_id} not found or user {request.user.username} lacks permission")
        messages.error(request, 'Booking not found or you do not have permission to cancel it.')
    return redirect('profile')


def about(request):
    return render(request, 'about.html')