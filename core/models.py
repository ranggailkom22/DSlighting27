from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Q


class Pelanggan(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    nama = models.CharField(max_length=100)
    alamat = models.TextField()
    nomor_telepon = models.CharField(max_length=15)
    email = models.EmailField()
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nama

    class Meta:
        verbose_name = "Pelanggan"
        verbose_name_plural = "Pelanggan"


class Paket(models.Model):
    nama = models.CharField(max_length=100)
    deskripsi = models.TextField()
    harga = models.DecimalField(max_digits=15, decimal_places=2)
    stok = models.PositiveIntegerField()
    gambar = models.ImageField(upload_to='paket_images/', blank=True, null=True)
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nama

    def is_available(self, jumlah_diminta):
        """
        Check if the package has sufficient physical stock
        Physical stock system: stock is deducted when ordered, restored when completed/cancelled
        """
        return self.stok >= jumlah_diminta

    class Meta:
        verbose_name = "Paket"
        verbose_name_plural = "Paket"


class Penyewaan(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Dikonfirmasi'),
        ('cancelled', 'Dibatalkan'),
        ('completed', 'Selesai'),
    ]
    
    pelanggan = models.ForeignKey(Pelanggan, on_delete=models.CASCADE)
    paket = models.ForeignKey(Paket, on_delete=models.SET_NULL, null=True, blank=True)
    tgl_pasang = models.DateTimeField()
    tgl_kembali = models.DateTimeField()
    ongkos_kirim = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    catatan = models.TextField(blank=True, null=True)
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Auto-calculate tgl_kembali as tgl_pasang + 1 day if not set
        if not self.tgl_kembali and self.tgl_pasang:
            self.tgl_kembali = self.tgl_pasang + timedelta(days=1)
        super().save(*args, **kwargs)

    @property
    def total_harga(self):
        """Calculate total price including shipping"""
        detail_total = self.detailpenyewaan_set.aggregate(
            total=Sum(models.F('jumlah') * models.F('harga_satuan'))
        )['total'] or 0
        return detail_total + self.ongkos_kirim

    def __str__(self):
        return f"Penyewaan {self.pelanggan.nama} - {self.paket.nama if self.paket else 'Paket Dihapus'}"

    class Meta:
        verbose_name = "Penyewaan"
        verbose_name_plural = "Penyewaan"
        indexes = [
            models.Index(fields=['tgl_pasang']),
            models.Index(fields=['status']),
            models.Index(fields=['pelanggan']),
            models.Index(fields=['tanggal_dibuat']),
        ]


class DetailPenyewaan(models.Model):
    penyewaan = models.ForeignKey(Penyewaan, on_delete=models.CASCADE)
    jumlah = models.PositiveIntegerField()
    harga_satuan = models.DecimalField(max_digits=15, decimal_places=2)

    @property
    def subtotal(self):
        """Calculate subtotal for this detail"""
        return (self.jumlah or 0) * (self.harga_satuan or 0)

    def save(self, *args, **kwargs):
        # Auto-populate harga_satuan from paket if not set
        if not self.harga_satuan and self.penyewaan.paket:
            self.harga_satuan = self.penyewaan.paket.harga
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Detail {self.penyewaan} - {self.jumlah} items"

    class Meta:
        verbose_name = "Detail Penyewaan"
        verbose_name_plural = "Detail Penyewaan"


class Transaksi(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Dibayar'),
        ('failed', 'Gagal'),
    ]
    
    penyewaan = models.ForeignKey(Penyewaan, on_delete=models.CASCADE)
    jumlah_bayar = models.DecimalField(max_digits=15, decimal_places=2)
    metode_pembayaran = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tanggal_transaksi = models.DateTimeField(auto_now_add=True)
    referensi_pembayaran = models.CharField(max_length=100, blank=True, null=True)
    bukti_bayar = models.ImageField(upload_to='bukti_bayar/', blank=True, null=True)

    def __str__(self):
        return f"Transaksi {self.penyewaan} - {self.jumlah_bayar}"

    class Meta:
        verbose_name = "Transaksi"
        verbose_name_plural = "Transaksi"
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['tanggal_transaksi']),
            models.Index(fields=['penyewaan']),
        ]


class Notifikasi(models.Model):
    JENIS_CHOICES = [
        ('info', 'Info'),
        ('warning', 'Peringatan'),
        ('danger', 'Bahaya'),
        ('success', 'Sukses'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    jenis = models.CharField(max_length=20, choices=JENIS_CHOICES, default='info')
    judul = models.CharField(max_length=100)
    pesan = models.TextField()
    sudah_dibaca = models.BooleanField(default=False)
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notifikasi: {self.judul}"

    class Meta:
        verbose_name = "Notifikasi"
        verbose_name_plural = "Notifikasi"
        ordering = ['-tanggal_dibuat']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['sudah_dibaca']),
            models.Index(fields=['tanggal_dibuat']),
        ]





