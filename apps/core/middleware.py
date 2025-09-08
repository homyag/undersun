from django.utils.deprecation import MiddlewareMixin


class PermissionsPolicyMiddleware(MiddlewareMixin):
    """
    Middleware to set Permissions Policy headers to allow unload events in admin
    This fixes the permissions policy violation in Django admin RelatedObjectLookups.js
    """
    
    def process_response(self, request, response):
        # Only apply to admin pages
        if request.path.startswith('/admin/'):
            # Allow unload event for admin pages to prevent violations
            # This is needed for Django's RelatedObjectLookups functionality
            response['Permissions-Policy'] = 'unload=*'
        
        return response