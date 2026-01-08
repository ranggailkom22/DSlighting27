from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Penyewaan, Transaksi, Notifikasi


@receiver(post_save, sender=Penyewaan)
def create_booking_notification(sender, instance, created, **kwargs):
    """
    Create notifications when a new booking is created
    """
    if created:
        # Create notification for admin
        Notifikasi.objects.create(
            user=None,  # For all admins
            jenis='info',
            judul='Pesanan Baru',
            pesan=f'Ada pesanan baru dari {instance.pelanggan.nama} untuk paket {instance.paket.nama}'
        )
        
        # Create notification for customer
        Notifikasi.objects.create(
            user=instance.pelanggan.user,
            jenis='success',
            judul='Pesanan Berhasil',
            pesan='Pesanan Anda berhasil dibuat, silakan unggah bukti bayar.'
        )


@receiver(post_save, sender=Transaksi)
def create_payment_notification(sender, instance, **kwargs):
    """
    Create notifications when payment status changes
    """
    # Check if this is an update (not creation) and status has changed
    if instance.pk:
        try:
            # Get the previous instance from database
            old_instance = Transaksi.objects.get(pk=instance.pk)
            # If status has changed
            if old_instance.status != instance.status:
                if instance.status == 'verified':  # Changed from 'confirmed' to 'verified'
                    # Payment verified
                    Notifikasi.objects.create(
                        user=instance.penyewaan.pelanggan.user,
                        jenis='success',
                        judul='Pembayaran Diterima',
                        pesan=f'Pembayaran untuk pesanan #{instance.penyewaan.id} telah diverifikasi. Pesanan Anda kini dikonfirmasi.'
                    )
                elif instance.status == 'failed':
                    # Payment rejected
                    Notifikasi.objects.create(
                        user=instance.penyewaan.pelanggan.user,
                        jenis='danger',
                        judul='Bukti Bayar Ditolak',
                        pesan='Bukti bayar ditolak, silakan unggah kembali.'
                    )
        except Transaksi.DoesNotExist:
            pass  # Handle case where instance was deleted