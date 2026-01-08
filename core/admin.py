from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import datetime
from django.shortcuts import render
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Pelanggan, Paket, Penyewaan, DetailPenyewaan, Transaksi, Notifikasi
from .utils import admin_dashboard_context
from urllib.parse import quote
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
from .utils import cancel_expired_pending_orders


class ActionMixin:
    """
    Mixin to add action column with edit, view, and delete icons
    """
    def get_action_column(self, obj, app_name, model_name):
        """
        Generate action column HTML with icons
        """
        edit_url = reverse(f'admin:{app_name}_{model_name}_change', args=[obj.pk])
        delete_url = reverse(f'admin:{app_name}_{model_name}_delete', args=[obj.pk])
        view_url = reverse(f'admin:{app_name}_{model_name}_change', args=[obj.pk])
        return format_html(
            '<a href="{}"><i class="fas fa-edit text-info" title="Edit"></i></a>&nbsp;'
            '<a href="{}"><i class="fas fa-eye text-primary" title="Lihat"></i></a>&nbsp;'
            '<a href="{}" class="text-danger"><i class="fas fa-trash" title="Hapus"></i></a>',
            edit_url, view_url, delete_url
        )


# Customize the default admin site
admin.site.site_header = "DSlighting27 Administration"
admin.site.site_title = "DSlighting27 Admin"
admin.site.index_title = "Industrial Dashboard"
admin.site.index_template = 'admin/index.html'


# Store the original index method
original_index = admin.site.index


# Override the default admin index view to include our dashboard context
def custom_index(request, extra_context=None):
    """
    Custom admin index view that includes dashboard data
    """
    context = admin_dashboard_context(request)
    if extra_context:
        context.update(extra_context)
    return original_index(request, context)


# Replace the admin site index method
admin.site.index = custom_index


@staff_member_required
@csrf_protect
def check_expired_orders(request):
    """
    AJAX endpoint to manually trigger expired orders cleanup
    """
    if request.method == 'POST':
        cancelled_count = cancel_expired_pending_orders()
        return JsonResponse({'cancelled_count': cancelled_count})
    return JsonResponse({'error': 'Method not allowed'}, status=405)


class DetailPenyewaanInline(admin.TabularInline):
    model = DetailPenyewaan
    extra = 1
    fields = ('jumlah', 'harga_satuan', 'get_subtotal')
    readonly_fields = ('get_subtotal',)

    def get_subtotal(self, obj):
        if obj.pk:  # Only calculate if the object has been saved
            return f"Rp {obj.subtotal:,}"
        return "-"
    get_subtotal.short_description = 'Subtotal'


class TransaksiInline(admin.TabularInline):
    model = Transaksi
    extra = 1


class PelangganAdmin(ActionMixin, admin.ModelAdmin):
    list_display = ['nama', 'email', 'nomor_telepon', 'alamat', 'aksi']
    list_filter = ['tanggal_dibuat']
    search_fields = ['nama', 'email', 'nomor_telepon']
    list_per_page = 20
    readonly_fields = ['tanggal_dibuat']

    def aksi(self, obj):
        return self.get_action_column(obj, 'core', 'pelanggan')
    aksi.short_description = 'Aksi'


class PaketAdmin(ActionMixin, admin.ModelAdmin):
    list_display = ['nama', 'harga', 'stok', 'aksi']
    list_filter = ['tanggal_dibuat']
    search_fields = ['nama', 'deskripsi']
    list_per_page = 20
    readonly_fields = ['tanggal_dibuat']
    actions = ['mark_units_as_broken']

    def mark_units_as_broken(self, request, queryset):
        """
        Decrease stock count for selected packages to account for broken/damaged units
        """
        updated_count = 0
        for paket in queryset:
            if paket.stok > 0:
                paket.stok -= 1
                paket.save()
                updated_count += 1
        
        self.message_user(
            request,
            f'{updated_count} paket berhasil diperbarui. Stok dikurangi untuk unit yang rusak.',
            messages.SUCCESS
        )
    
    mark_units_as_broken.short_description = "Mark 1 Unit as Broken (Decrease Stock)"

    def aksi(self, obj):
        return self.get_action_column(obj, 'core', 'paket')
    aksi.short_description = 'Aksi'


class PenyewaanAdmin(ActionMixin, admin.ModelAdmin):
    list_display = ['pelanggan', 'paket', 'tgl_pasang', 'status_badge', 'status_pembayaran', 'whatsapp_button', 'aksi']
    list_filter = ['status', 'tgl_pasang', 'tanggal_dibuat']
    search_fields = ['pelanggan__nama', 'paket__nama']
    list_per_page = 20
    readonly_fields = ['total_harga', 'tanggal_dibuat']
    inlines = [DetailPenyewaanInline, TransaksiInline]

    def status_badge(self, obj):
        color_map = {
            'pending': 'warning',
            'confirmed': 'primary',
            'cancelled': 'danger',
            'completed': 'success'
        }
        color = color_map.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def status_pembayaran(self, obj):
        total_bayar = obj.transaksi_set.filter(status='paid').aggregate(
            total=Sum('jumlah_bayar')
        )['total'] or 0
        
        if total_bayar >= obj.total_harga:
            return format_html('<span class="badge badge-success">Lunas</span>')
        elif total_bayar > 0:
            return format_html('<span class="badge badge-warning">Sebagian</span>')
        else:
            return format_html('<span class="badge badge-danger">Belum Bayar</span>')
    status_pembayaran.short_description = 'Pembayaran'

    def whatsapp_button(self, obj):
        # Format phone number (replace leading 0 with 62)
        phone = obj.pelanggan.nomor_telepon
        if phone.startswith('0'):
            phone = '62' + phone[1:]
        
        # Create WhatsApp message
        message = f"Halo {obj.pelanggan.nama}, Status penyewaan Anda #{obj.id} sekarang adalah {obj.get_status_display()}. Terima kasih - DSlighting27"
        encoded_message = quote(message)
        
        whatsapp_url = f"https://wa.me/{phone}?text={encoded_message}"
        
        return format_html(
            '<a href="{}" target="_blank" class="btn btn-success btn-sm"><i class="fab fa-whatsapp"></i> WhatsApp</a>',
            whatsapp_url
        )
    whatsapp_button.short_description = 'Kontak WA'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.prefetch_related('transaksi_set')

    def aksi(self, obj):
        return self.get_action_column(obj, 'core', 'penyewaan')
    aksi.short_description = 'Aksi'


class DetailPenyewaanAdmin(ActionMixin, admin.ModelAdmin):
    list_display = ['penyewaan', 'jumlah', 'harga_satuan', 'get_subtotal', 'aksi']
    list_filter = ['penyewaan__tgl_pasang']
    search_fields = ['penyewaan__pelanggan__nama', 'penyewaan__paket__nama']
    list_per_page = 20
    readonly_fields = ['get_subtotal']

    def get_subtotal(self, obj):
        if obj.pk:  # Only calculate if the object has been saved
            return f"Rp {obj.subtotal:,}"
        return "-"
    get_subtotal.short_description = 'Subtotal'

    def aksi(self, obj):
        return self.get_action_column(obj, 'core', 'detailpenyewaan')
    aksi.short_description = 'Aksi'


class TransaksiAdmin(ActionMixin, admin.ModelAdmin):
    list_display = ['penyewaan', 'jumlah_bayar', 'metode_pembayaran', 'status', 'bukti_bayar_thumbnail', 'whatsapp_button', 'aksi']
    list_filter = ['status', 'metode_pembayaran', 'tanggal_transaksi']
    search_fields = ['penyewaan__pelanggan__nama', 'referensi_pembayaran']
    list_per_page = 20
    readonly_fields = ['tanggal_transaksi', 'bukti_bayar_preview']

    def bukti_bayar_thumbnail(self, obj):
        if obj.bukti_bayar:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="width: 100px; height: auto;"/></a>',
                obj.bukti_bayar.url,
                obj.bukti_bayar.url
            )
        return "Tidak ada"
    bukti_bayar_thumbnail.short_description = 'Bukti Bayar'

    def bukti_bayar_preview(self, obj):
        if obj.bukti_bayar:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-width: 300px; height: auto;"/></a>',
                obj.bukti_bayar.url,
                obj.bukti_bayar.url
            )
        return "Tidak ada bukti pembayaran"
    bukti_bayar_preview.short_description = 'Preview Bukti Bayar'

    def whatsapp_button(self, obj):
        # Format phone number (replace leading 0 with 62)
        phone = obj.penyewaan.pelanggan.nomor_telepon
        if phone.startswith('0'):
            phone = '62' + phone[1:]
        
        # Create WhatsApp message based on status
        if obj.status == 'paid':
            message = f"Halo {obj.penyewaan.pelanggan.nama}, Bukti pembayaran Anda untuk penyewaan #{obj.penyewaan.id} sedang diverifikasi. Terima kasih - DSlighting27"
        elif obj.status == 'confirmed':
            message = f"Halo {obj.penyewaan.pelanggan.nama}, Pembayaran untuk penyewaan #{obj.penyewaan.id} telah diverifikasi. Terima kasih - DSlighting27"
        elif obj.status == 'failed':
            message = f"Halo {obj.penyewaan.pelanggan.nama}, Bukti pembayaran untuk penyewaan #{obj.penyewaan.id} ditolak. Silakan unggah kembali. Terima kasih - DSlighting27"
        else:
            message = f"Halo {obj.penyewaan.pelanggan.nama}, Terima kasih atas pembayaran Anda untuk penyewaan #{obj.penyewaan.id}. Terima kasih - DSlighting27"
        
        encoded_message = quote(message)
        whatsapp_url = f"https://wa.me/{phone}?text={encoded_message}"
        
        return format_html(
            '<a href="{}" target="_blank" class="btn btn-success btn-sm"><i class="fab fa-whatsapp"></i> WhatsApp</a>',
            whatsapp_url
        )
    whatsapp_button.short_description = 'Kontak WA'

    def aksi(self, obj):
        return self.get_action_column(obj, 'core', 'transaksi')
    aksi.short_description = 'Aksi'


class NotifikasiAdmin(ActionMixin, admin.ModelAdmin):
    list_display = ['judul', 'jenis', 'user', 'sudah_dibaca', 'aksi']
    list_filter = ['jenis', 'sudah_dibaca', 'tanggal_dibuat']
    search_fields = ['judul', 'pesan', 'user__username']
    list_per_page = 20
    readonly_fields = ['tanggal_dibuat']

    def aksi(self, obj):
        return self.get_action_column(obj, 'core', 'notifikasi')
    aksi.short_description = 'Aksi'


# Register models with default admin
admin.site.register(Pelanggan, PelangganAdmin)
admin.site.register(Paket, PaketAdmin)
admin.site.register(Penyewaan, PenyewaanAdmin)
admin.site.register(DetailPenyewaan, DetailPenyewaanAdmin)
admin.site.register(Transaksi, TransaksiAdmin)
admin.site.register(Notifikasi, NotifikasiAdmin)


# Custom admin URLs
from django.urls import path

def get_admin_urls(urls):
    def get_urls():
        my_urls = [
            path('check-expired-orders/', check_expired_orders, name='check_expired_orders'),
        ]
        return my_urls + urls
    return get_urls

admin.site.get_urls = get_admin_urls(admin.site.get_urls())
