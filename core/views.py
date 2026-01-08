from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.db import transaction
from django.utils import timezone
from datetime import datetime
from .models import Paket, Pelanggan, Penyewaan, DetailPenyewaan, Transaksi
from decimal import Decimal
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime
import json


def landing_page(request):
    """
    Display the landing page with all available packages
    """
    paket_list = Paket.objects.all()
    return render(request, 'frontend/landing.html', {'paket_list': paket_list})


def login_view(request):
    """
    Handle user login
    """
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Login berhasil!')
            return redirect('customer_dashboard')
        else:
            messages.error(request, 'Username atau password salah!')
    
    return render(request, 'frontend/login.html')


def register_view(request):
    """
    Handle user registration
    """
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        email = request.POST['email']
        phone = request.POST['phone']
        address = request.POST['address']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        
        # Validation
        if password1 != password2:
            messages.error(request, 'Password tidak cocok!')
            return render(request, 'frontend/register.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username sudah digunakan!')
            return render(request, 'frontend/register.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email sudah terdaftar!')
            return render(request, 'frontend/register.html')
        
        # Create user and customer in a transaction
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1,
                    first_name=first_name,
                    last_name=last_name
                )
                
                Pelanggan.objects.create(
                    user=user,
                    nama=f"{first_name} {last_name}",
                    alamat=address,
                    nomor_telepon=phone,
                    email=email
                )
                
                messages.success(request, 'Registrasi berhasil! Silakan login.')
                return redirect('login')
        except Exception as e:
            messages.error(request, 'Terjadi kesalahan saat registrasi. Silakan coba lagi.')
            return render(request, 'frontend/register.html')
    
    return render(request, 'frontend/register.html')


@login_required
def booking_view(request, paket_id):
    """
    Handle booking process for a package with atomic locking to prevent race conditions
    Physical stock system: stock is deducted immediately upon booking
    """
    if request.method == 'POST':
        tgl_pasang_str = request.POST['tgl_pasang']
        jumlah = int(request.POST.get('jumlah', 1))
        catatan = request.POST.get('catatan', '')
        
        # Parse date
        try:
            tgl_pasang = timezone.make_aware(datetime.strptime(tgl_pasang_str, '%Y-%m-%d'))
        except ValueError:
            messages.error(request, 'Format tanggal tidak valid!')
            paket = get_object_or_404(Paket, id=paket_id)
            return render(request, 'frontend/booking.html', {'paket': paket})
        
        # Create booking in a transaction with row-level locking
        try:
            with transaction.atomic():
                # 1. Lock the paket row to prevent race conditions
                paket = Paket.objects.select_for_update().get(id=paket_id)
                
                # 2. Validate physical stock availability
                if not paket.is_available(jumlah):
                    messages.error(request, f'Maaf, stok tidak mencukupi. Stok tersedia: {paket.stok} unit')
                    return render(request, 'frontend/booking.html', {'paket': paket})
                
                # Get or create pelanggan
                try:
                    pelanggan = request.user.pelanggan
                except Pelanggan.DoesNotExist:
                    messages.error(request, 'Data pelanggan tidak ditemukan!')
                    return redirect('landing_page')
                
                # 3. Deduct physical stock immediately
                paket.stok -= jumlah
                paket.save()
                
                # 4. Create penyewaan
                penyewaan = Penyewaan.objects.create(
                    pelanggan=pelanggan,
                    paket=paket,
                    tgl_pasang=tgl_pasang,
                    ongkos_kirim=Decimal('0.00'),  # Default shipping cost
                    catatan=catatan,
                    status='pending'
                )
                
                # 5. Create detail penyewaan
                DetailPenyewaan.objects.create(
                    penyewaan=penyewaan,
                    jumlah=jumlah,
                    harga_satuan=paket.harga
                )
                
                # 6. Create initial transaction
                Transaksi.objects.create(
                    penyewaan=penyewaan,
                    jumlah_bayar=penyewaan.total_harga,
                    metode_pembayaran='Transfer Bank',
                    status='pending'
                )
                
                messages.success(request, 'Pemesanan berhasil dibuat! Silakan lanjutkan ke pembayaran dalam 2 jam.')
                return redirect('customer_dashboard')
                
        except Paket.DoesNotExist:
            messages.error(request, 'Paket tidak ditemukan!')
            return redirect('landing_page')
        except Exception as e:
            messages.error(request, 'Terjadi kesalahan saat membuat pemesanan. Silakan coba lagi.')
            paket = get_object_or_404(Paket, id=paket_id)
            return render(request, 'frontend/booking.html', {'paket': paket})
    
    # GET request - show booking form
    paket = get_object_or_404(Paket, id=paket_id)
    return render(request, 'frontend/booking.html', {'paket': paket})


@login_required
def update_profile_view(request):
    """
    Handle profile update for user and customer data
    """
    if request.method == 'POST':
        # Update user data
        user = request.user
        user.first_name = request.POST.get('first_name', user.first_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        
        # Update customer data
        try:
            pelanggan = user.pelanggan
            pelanggan.alamat = request.POST.get('alamat', pelanggan.alamat)
            pelanggan.nomor_telepon = request.POST.get('nomor_telepon', pelanggan.nomor_telepon)
            pelanggan.save()
            
            # Return success response
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Profil berhasil diperbarui!'})
            else:
                messages.success(request, 'Profil berhasil diperbarui!')
                return redirect('customer_dashboard')
        except Pelanggan.DoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Data pelanggan tidak ditemukan!'}, status=400)
            else:
                messages.error(request, 'Data pelanggan tidak ditemukan!')
                return redirect('customer_dashboard')
    
    # For GET requests, redirect to dashboard
    return redirect('customer_dashboard')


@login_required
def upload_payment_view(request, penyewaan_id):
    """
    Handle payment evidence upload for a rental
    """
    penyewaan = get_object_or_404(Penyewaan, id=penyewaan_id, pelanggan__user=request.user)
    
    # Get the transaction for this rental
    try:
        transaksi = Transaksi.objects.get(penyewaan=penyewaan)
    except Transaksi.DoesNotExist:
        messages.error(request, 'Data transaksi tidak ditemukan!')
        return redirect('customer_dashboard')
    
    if request.method == 'POST':
        bukti_bayar = request.FILES.get('bukti_bayar')
        
        if bukti_bayar:
            # Validate file type and size
            allowed_types = ['image/jpeg', 'image/png', 'image/gif']
            max_size = 5 * 1024 * 1024  # 5MB
            
            if bukti_bayar.content_type not in allowed_types:
                messages.error(request, 'Format file tidak didukung. Silakan unggah file JPG, PNG, atau GIF.')
                return render(request, 'frontend/payment_upload.html', {
                    'penyewaan': penyewaan,
                    'transaksi': transaksi
                })
            
            if bukti_bayar.size > max_size:
                messages.error(request, 'Ukuran file terlalu besar. Maksimal 5MB.')
                return render(request, 'frontend/payment_upload.html', {
                    'penyewaan': penyewaan,
                    'transaksi': transaksi
                })
            
            # Update transaction with payment evidence
            transaksi.bukti_bayar = bukti_bayar
            transaksi.status = 'paid'  # Set status to paid after uploading evidence
            transaksi.save()
            
            messages.success(request, 'Bukti pembayaran berhasil diunggah! Menunggu verifikasi admin.')
            return redirect('customer_dashboard')
        else:
            messages.error(request, 'Silakan pilih file bukti pembayaran!')
    
    return render(request, 'frontend/payment_upload.html', {
        'penyewaan': penyewaan,
        'transaksi': transaksi
    })


@login_required
def customer_dashboard(request):
    """
    Display customer dashboard with their rentals
    """
    # Get penyewaan for the current user
    penyewaan_list = Penyewaan.objects.filter(pelanggan__user=request.user).order_by('-tanggal_dibuat')
    
    # Get transactions for each rental
    transaksi_dict = {}
    for penyewaan in penyewaan_list:
        try:
            transaksi = Transaksi.objects.get(penyewaan=penyewaan)
            transaksi_dict[penyewaan.id] = transaksi
        except Transaksi.DoesNotExist:
            transaksi_dict[penyewaan.id] = None
    
    return render(request, 'frontend/dashboard.html', {
        'penyewaan_list': penyewaan_list,
        'transaksi_dict': transaksi_dict
    })


@csrf_exempt
def notifications_api(request):
    """
    API endpoint to get user notifications
    """
    if request.method == 'GET':
        if request.user.is_authenticated:
            notifications = Notifikasi.objects.filter(
                user=request.user
            ).order_by('-tanggal_dibuat')[:10]
            
            notifications_data = []
            for notification in notifications:
                notifications_data.append({
                    'id': notification.id,
                    'judul': notification.judul,
                    'pesan': notification.pesan,
                    'jenis': notification.jenis,
                    'sudah_dibaca': notification.sudah_dibaca,
                    'tanggal_dibuat': notification.tanggal_dibuat.isoformat()
                })
            
            return JsonResponse({
                'notifications': notifications_data,
                'count': len(notifications_data)
            })
        else:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def mark_notification_as_read(request, notification_id):
    """
    API endpoint to mark a notification as read
    """
    if request.method == 'POST':
        if request.user.is_authenticated:
            try:
                notification = Notifikasi.objects.get(
                    id=notification_id,
                    user=request.user
                )
                notification.sudah_dibaca = True
                notification.save()
                
                return JsonResponse({'success': True})
            except Notifikasi.DoesNotExist:
                return JsonResponse({'error': 'Notification not found'}, status=404)
        else:
            return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)
