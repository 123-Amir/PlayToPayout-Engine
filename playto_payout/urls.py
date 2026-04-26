"""
URL configuration for playto_payout project.
"""
from django.contrib import admin
from django.urls import path, include
from django.http import HttpResponse
from rest_framework.routers import DefaultRouter
from ledger.views import MerchantViewSet, PayoutViewSet, LedgerEntryViewSet

router = DefaultRouter()
router.register(r'merchants', MerchantViewSet)
router.register(r'payouts', PayoutViewSet)
router.register(r'ledger-entries', LedgerEntryViewSet)

def home(request):
    return HttpResponse("""
    <h1>Welcome to Play to Payout Engine</h1>
    <p>API endpoints:</p>
    <ul>
        <li><a href="/admin/">Admin</a></li>
        <li><a href="/api/v1/">API v1</a></li>
        <li><a href="/api-auth/">API Auth</a></li>
    </ul>
    <p>To run the dashboard, navigate to the dashboard folder and run: npm run dev</p>
    """)

urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    path('api/v1/', include(router.urls)),
    path('api-auth/', include('rest_framework.urls')),
]
