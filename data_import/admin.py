from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import ImportFile, ImportLog, PropertyImportMapping


class ImportLogInline(admin.TabularInline):
    model = ImportLog
    extra = 0
    readonly_fields = ['level', 'message', 'row_number', 'details', 'created_at']
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(ImportFile)
class ImportFileAdmin(admin.ModelAdmin):
    list_display = ['name', 'import_type', 'status', 'success_rate_display', 'uploaded_by', 'created_at']
    list_filter = ['import_type', 'status', 'created_at', 'uploaded_by']
    readonly_fields = ['name', 'total_rows', 'processed_rows', 'successful_rows', 'failed_rows', 
                      'success_rate_display', 'parsed_data_display', 'validation_errors_display',
                      'created_at', 'started_at', 'completed_at']
    fields = ['name', 'file', 'import_type', 'status', 'uploaded_by',
             ('total_rows', 'processed_rows', 'successful_rows', 'failed_rows'),
             'success_rate_display', 'parsed_data_display', 'validation_errors_display',
             ('created_at', 'started_at', 'completed_at')]
    inlines = [ImportLogInline]
    
    def success_rate_display(self, obj):
        rate = obj.success_rate
        if rate == 100:
            color = 'green'
        elif rate >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    success_rate_display.short_description = 'Успешность'
    
    def parsed_data_display(self, obj):
        if obj.parsed_data:
            return format_html(
                '<details><summary>Показать данные ({} записей)</summary><pre>{}</pre></details>',
                len(obj.parsed_data) if isinstance(obj.parsed_data, list) else 'N/A',
                str(obj.parsed_data)[:1000] + '...' if len(str(obj.parsed_data)) > 1000 else str(obj.parsed_data)
            )
        return 'Нет данных'
    parsed_data_display.short_description = 'Распарсенные данные'
    
    def validation_errors_display(self, obj):
        if obj.validation_errors:
            errors_count = len(obj.validation_errors)
            return format_html(
                '<details><summary style="color: red;">Показать ошибки ({})</summary><pre>{}</pre></details>',
                errors_count,
                '\n'.join([f"Строка {err.get('row', 'N/A')}: {err.get('field', 'N/A')} - {err.get('error', 'N/A')}" 
                          for err in obj.validation_errors[:10]])
            )
        return 'Нет ошибок'
    validation_errors_display.short_description = 'Ошибки валидации'
    
    def has_add_permission(self, request):
        return False


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ['import_file', 'level', 'message_short', 'row_number', 'created_at']
    list_filter = ['level', 'import_file', 'created_at']
    readonly_fields = ['import_file', 'level', 'message', 'row_number', 'details', 'created_at']
    
    def message_short(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_short.short_description = 'Сообщение'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PropertyImportMapping)
class PropertyImportMappingAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_default', 'mapped_fields_count', 'created_at']
    list_filter = ['is_default', 'created_at']
    fields = ['name', 'description', 'is_default', 
             ('header_row', 'data_start_row'),
             'field_mapping_display', 'field_mapping']
    readonly_fields = ['field_mapping_display', 'created_at', 'updated_at']
    
    def mapped_fields_count(self, obj):
        count = len(obj.get_mapped_fields())
        return f"{count} полей"
    mapped_fields_count.short_description = 'Замапленные поля'
    
    def field_mapping_display(self, obj):
        if obj.field_mapping:
            mapping_html = '<table border="1" style="border-collapse: collapse;">'
            mapping_html += '<tr><th>Excel колонка</th><th>Поле модели</th></tr>'
            for excel_col, model_field in obj.field_mapping.items():
                mapping_html += f'<tr><td>{excel_col}</td><td>{model_field}</td></tr>'
            mapping_html += '</table>'
            return mark_safe(mapping_html)
        return 'Маппинг не настроен'
    field_mapping_display.short_description = 'Текущий маппинг'
