import json
from .models import Pelanggan, Paket, Penyewaan, DetailPenyewaan, Transaksi, Notifikasi
from django.db.models import Sum, Count
from calendar import month_name
from django.utils import timezone
from datetime import timedelta


def cancel_expired_pending_orders():
    """
    Cancel pending orders that have not been paid within 2 hours
    Only cancel if there's no payment proof uploaded
    This releases the reserved stock for other customers
    Physical stock system: stock is restored when order is cancelled
    """
    # Get pending orders older than 2 hours that don't have payment proof
    expiry_time = timezone.now() - timedelta(hours=2)
    
    expired_orders = Penyewaan.objects.filter(
        status='pending',
        tanggal_dibuat__lt=expiry_time
    ).exclude(
        transaksi__bukti_bayar__isnull=False
    )
    
    cancelled_count = 0
    for order in expired_orders:
        # Restore physical stock before cancelling
        detail = order.detailpenyewaan_set.first()
        if detail and order.paket:
            order.paket.stok += detail.jumlah
            order.paket.save()
        
        # Update order status to cancelled
        order.status = 'cancelled'
        order.save()
        
        # Create notification for the customer
        Notifikasi.objects.create(
            user=order.pelanggan.user,
            jenis='warning',
            judul='Pesanan Dibatalkan',
            pesan=f'Pesanan #{order.id} dibatalkan karena tidak ada pembayaran dalam 2 jam. Stok telah dikembalikan ke gudang.'
        )
        
        cancelled_count += 1
    
    return cancelled_count


def admin_dashboard_context(request):
    """
    Provide context data for the admin dashboard
    """
    # Aggregated cards data
    total_pelanggan = Pelanggan.objects.count()
    total_paket = Paket.objects.count()
    total_penyewaan_sukses = Penyewaan.objects.filter(status='completed').count()
    
    # Transactions needing verification (paid but not confirmed)
    transactions_needing_verification = Transaksi.objects.filter(status='paid').count()
    
    # Orders needing processing (pending status)
    orders_needing_processing = Penyewaan.objects.filter(status='pending').count()
    
    # Total pendapatan from valid transactions
    total_pendapatan = Transaksi.objects.filter(status='paid').aggregate(
        total=Sum('jumlah_bayar')
    )['total'] or 0
    
    # Chart Data: Monthly Revenue for the last 6 months
    now = timezone.now()
    monthly_revenue = []
    months = []
    revenues = []
    
    for i in range(5, -1, -1):  # Last 6 months
        month = now.month - i
        year = now.year
        
        if month <= 0:
            month += 12
            year -= 1
            
        # Get revenue for this month
        revenue = Transaksi.objects.filter(
            status='paid',
            tanggal_transaksi__year=year,
            tanggal_transaksi__month=month
        ).aggregate(total=Sum('jumlah_bayar'))['total'] or 0
        
        months.append(f"{month_name[month][:3]} {year}")
        revenues.append(float(revenue))
    
    # Top 3 Packages by rental count
    top_packages = Paket.objects.annotate(
        rental_count=Count('penyewaan')
    ).order_by('-rental_count')[:3]
    
    return {
        'total_pelanggan': total_pelanggan,
        'total_paket': total_paket,
        'total_penyewaan_sukses': total_penyewaan_sukses,
        'transactions_needing_verification': transactions_needing_verification,
        'orders_needing_processing': orders_needing_processing,
        'total_pendapatan': total_pendapatan,
        'months_json': json.dumps(months),
        'revenues_json': json.dumps(revenues),
        'top_packages': top_packages,
    }