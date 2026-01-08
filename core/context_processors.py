from .models import Notifikasi


def notifications_processor(request):
    """
    Context processor to handle unread notification counts for both admin and customers
    """
    unread_count = 0
    
    if request.user.is_authenticated:
        if request.user.is_staff:
            # For admin users, show all unread notifications
            unread_count = Notifikasi.objects.filter(sudah_dibaca=False).count()
        else:
            # For customer users, show their unread notifications
            unread_count = Notifikasi.objects.filter(
                user=request.user,
                sudah_dibaca=False
            ).count()
    else:
        # For anonymous users, check session-based notifications if any
        # This would be implemented based on specific business logic
        pass
    
    return {
        'unread_notifications_count': unread_count
    }