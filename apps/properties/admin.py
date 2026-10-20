from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponseRedirect
from django import forms
from django.forms import ModelForm
from django.utils.html import format_html
from django.db.models import Q
from tinymce.widgets import TinyMCE
# from modeltranslation.admin import TranslationAdmin
from .models import (
    Property, PropertyImage, PropertyType, Developer,
    PropertyFeature, PropertyFeatureRelation
)
from .services import translate_property, translate_property_type, translate_developer, translate_property_feature


class TranslationStatusFilter(admin.SimpleListFilter):
    title = 'Статус перевода'
    parameter_name = 'translation_status'

    def lookups(self, request, model_admin):
        return (
            ('missing', 'Нет перевода'),
            ('partial', 'Частичный перевод'),
            ('complete', 'Полный перевод'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        empty_en_title = Q(title_en__isnull=True) | Q(title_en__exact='')
        empty_en_desc = Q(description_en__isnull=True) | Q(description_en__exact='')
        empty_th_title = Q(title_th__isnull=True) | Q(title_th__exact='')
        empty_th_desc = Q(description_th__isnull=True) | Q(description_th__exact='')

        missing_filter = empty_en_title & empty_en_desc & empty_th_title & empty_th_desc
        complete_filter = (
            ~empty_en_title & ~empty_en_desc &
            ~empty_th_title & ~empty_th_desc
        )

        if value == 'missing':
            return queryset.filter(missing_filter)
        if value == 'complete':
            return queryset.filter(complete_filter)
        if value == 'partial':
            return queryset.exclude(missing_filter).exclude(complete_filter)
        return queryset
from .widgets import BulkImageUploadWidget


class BaseAdminWithRequiredFields(admin.ModelAdmin):
    """Базовый класс админ-панели с подключением стилей для обязательных полей"""
    
    class Media:
        css = {
            'all': ('admin/css/required_fields.css',)
        }
        js = ('admin/js/required_fields.js',)
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """Добавляем CSS класс 'required' для обязательных полей"""
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        
        # Проверяем, является ли поле обязательным
        if formfield and not db_field.blank and not db_field.null:
            if hasattr(formfield.widget, 'attrs'):
                formfield.widget.attrs['class'] = formfield.widget.attrs.get('class', '') + ' required-field'
        
        return formfield


class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1
    fields = (
        'drag_handle', 'image_preview', 'image', 'title', 'frame_type', 'is_main',
        'alt_text', 'alt_text_ru', 'alt_text_en', 'alt_text_th',
        'alt_generated_by', 'alt_confidence', 'alt_generated_at',
        'order',
    )
    readonly_fields = ('drag_handle', 'image_preview', 'alt_generated_at')
    
    class Media:
        css = {
            'all': ('admin/css/sortable_images.css',)
        }
        js = ('https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js', 'admin/js/sortable_images.js')
    
    def drag_handle(self, obj):
        """Ручка для перетаскивания"""
        return format_html(
            '<span class="drag-handle" style="cursor: grab; font-size: 18px; color: #666; user-select: none;">⋮⋮</span>'
        )
    drag_handle.short_description = '↕️'
    
    def image_preview(self, obj):
        """Отображение превью изображения в админке"""
        if obj.image:
            try:
                image_url = obj.image.url
            except Exception:
                return format_html('<div style="color: #999; font-style: italic;">Файл недоступен</div>')

            # Определяем стили для главного изображения
            border_style = 'border: 3px solid #28a745;' if obj.is_main else 'border: 1px solid #ddd;'
            
            # Создаем звездочку для главного изображения отдельно
            star_html = format_html(
                '<span style="position: absolute; top: -5px; right: -5px; background: #28a745; color: white; border-radius: 50%; width: 18px; height: 18px; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: bold;">★</span>'
            ) if obj.is_main else format_html('')
            
            return format_html(
                '''
                <div style="position: relative;">
                    <a href="{}" target="_blank">
                        <img src="{}" alt="{}" 
                             style="width: 100px; height: 75px; object-fit: cover; border-radius: 4px; {}" />
                    </a>
                    {}
                    <div style="font-size: 10px; margin-top: 2px; color: #666;">
                        Порядок: {} {}
                    </div>
                </div>
                ''',
                image_url,
                image_url,
                obj.title or 'Изображение',
                border_style,
                star_html,
                obj.order,
                '| ГЛАВНОЕ' if obj.is_main else ''
            )
        return format_html('<div style="color: #999; font-style: italic;">Нет изображения</div>')
    image_preview.short_description = '📷 Превью'
    
    class Meta:
        verbose_name = 'Изображение'
        verbose_name_plural = 'Изображения'


class PropertyFeatureInline(admin.TabularInline):
    model = PropertyFeatureRelation
    extra = 1


class PropertyAdminForm(forms.ModelForm):
    """Форма для Property с кастомными виджетами"""
    
    class Meta:
        model = Property
        fields = '__all__'
        widgets = {
            # Поле description использует TinyMCE
            'description': TinyMCE(attrs={'class': 'tinymce-content'}),
        }


@admin.register(Property)
class PropertyAdmin(BaseAdminWithRequiredFields):
    form = PropertyAdminForm
    list_display = (
        'legacy_id', 'title', 'property_type', 'district', 'deal_type', 'build_status',
        'price_sale_thb', 'special_offer', 'is_active', 'is_featured',
        'featured_priority', 'views_count', 'created_at', 'translation_status'
    )
    # Новые черновики из AREALISTING ещё не имеют legacy_id.  Оставляем ссылку
    # и на ID, и на название, чтобы такую карточку всегда можно было открыть.
    list_display_links = ('legacy_id', 'title')
    list_filter = (
        'is_active', 'property_type', 'district', 'deal_type',
        'status', 'is_featured', 'furnished', TranslationStatusFilter
    )
    search_fields = ('legacy_id', 'title', 'description', 'address')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [PropertyImageInline, PropertyFeatureInline]
    list_editable = ('property_type', 'is_active', 'is_featured', 'featured_priority', 'build_status')
    date_hierarchy = 'created_at'
    ordering = ('-featured_priority', '-created_at')
    
    actions = ['make_active', 'make_inactive', 'make_featured', 'make_not_featured', 'auto_translate', 'force_retranslate']

    readonly_fields = ('translation_status_note', 'arealisting_sync_note')

    def arealisting_sync_note(self, obj):
        if not obj or not obj.pk:
            return 'Связь появится после создания карточки.'
        from django.urls import reverse
        from apps.arealisting.models import ArealistingListingGroup, ArealistingPriceReview

        try:
            group = obj.arealisting_group
        except ArealistingListingGroup.DoesNotExist:
            picker_url = reverse('admin:arealisting_unlinked')
            history_url = reverse('admin:arealisting_arealistingpropertychange_changelist')
            return format_html(
                'Карточка не связана с AREALISTING. '
                '<a href="{}?property={}">Подобрать комплекс</a> · '
                '<a href="{}?card={}">История изменений</a>',
                picker_url,
                obj.pk,
                history_url,
                obj.pk,
            )

        from apps.arealisting.services.field_ownership import (
            SOURCE_FIELD_LABELS,
            ordered_source_fields,
        )

        managed = ordered_source_fields(group.source_owned_fields)
        locked = ordered_source_fields(group.locked_fields)
        managed_text = ', '.join(SOURCE_FIELD_LABELS.get(field, field) for field in managed) or 'нет'
        locked_text = ', '.join(SOURCE_FIELD_LABELS.get(field, field) for field in locked) or 'нет'
        url = reverse('admin:arealisting_arealistinglistinggroup_change', args=[group.pk])
        detach_url = reverse('admin:arealisting_detach_property', args=[obj.pk])
        history_url = reverse('admin:arealisting_arealistingpropertychange_changelist')
        readiness_url = reverse('admin:arealisting_arealistinglistinggroup_readiness', args=[group.pk])
        readiness_link = (
            format_html('<a href="{}">Проверить перед публикацией</a> · ', readiness_url)
            if group.catalog_origin == ArealistingListingGroup.CatalogOrigin.AREALISTING_DRAFT else ''
        )
        pending_price = ArealistingPriceReview.objects.filter(
            group=group, status=ArealistingPriceReview.Status.PENDING,
        ).first()
        price_link = (
            format_html('<a href="{}">Проверить новую цену</a> · ',
                        reverse('admin:arealisting_arealistingpricereview_review', args=[pending_price.pk]))
            if pending_price else ''
        )
        return format_html(
            '<div><strong>Управляет AREALISTING:</strong> {}<br>'
            '<strong>Защищено вручную:</strong> {}<br>'
            '{}{}<a href="{}">Настроить защиту полей</a> · '
            '<a href="{}">Отвязать от AREALISTING</a> · '
            '<a href="{}?card={}">История изменений</a></div>',
            managed_text,
            locked_text,
            readiness_link,
            price_link,
            url,
            detach_url,
            history_url,
            obj.pk,
        )

    arealisting_sync_note.short_description = 'Синхронизация AREALISTING'
    
    def make_active(self, request, queryset):
        """Сделать недвижимость активной (опубликованной)"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} объектов недвижимости опубликовано.')
    make_active.short_description = "✅ Опубликовать выбранные объекты"
    
    def make_inactive(self, request, queryset):
        """Снять недвижимость с публикации"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} объектов недвижимости снято с публикации.')
    make_inactive.short_description = "❌ Снять с публикации выбранные объекты"
    
    def make_featured(self, request, queryset):
        """Сделать недвижимость рекомендуемой"""
        updated = queryset.update(is_featured=True)
        self.message_user(request, f'{updated} объектов недвижимости добавлено в рекомендуемые.')
    make_featured.short_description = "⭐ Добавить в рекомендуемые"
    
    def make_not_featured(self, request, queryset):
        """Убрать из рекомендуемых"""
        updated = queryset.update(is_featured=False)
        self.message_user(request, f'{updated} объектов недвижимости убрано из рекомендуемых.')
    make_not_featured.short_description = "⚪ Убрать из рекомендуемых"

    # --- Перевод ---

    @staticmethod
    def _compute_translation_status(obj):
        if not obj:
            return '⛔', 'Нет перевода', '#94a3b8'

        required_pairs = [
            ('title_en', 'description_en'),
            ('title_th', 'description_th'),
        ]

        completed = 0
        partially = False
        for title_field, description_field in required_pairs:
            raw_title = getattr(obj, title_field, '')
            raw_description = getattr(obj, description_field, '')

            title_value = raw_title if isinstance(raw_title, str) else ('' if raw_title in (None, False) else str(raw_title))
            description_value = raw_description if isinstance(raw_description, str) else ('' if raw_description in (None, False) else str(raw_description))

            has_title = bool(title_value.strip())
            has_description = bool(description_value.strip())
            if has_title and has_description:
                completed += 1
            elif has_title or has_description:
                partially = True

        if completed == len(required_pairs):
            return '✅', 'Перевод готов', '#22c55e'
        if completed > 0 or partially:
            return '⚠️', 'Частичный перевод', '#facc15'
        return '⛔', 'Нет перевода', '#94a3b8'

    def translation_status(self, obj):
        icon, label, color = self._compute_translation_status(obj)
        return format_html(
            '<span title="{}" style="color:{}; font-weight:600;">{}</span>',
            label,
            color,
            icon,
        )

    translation_status.short_description = 'Статус перевода'
    translation_status.allow_tags = True

    def translation_status_note(self, obj):
        icon, label, color = self._compute_translation_status(obj)
        return format_html(
            '<span style="display:inline-flex; align-items:center; gap:8px; color:{color}; font-weight:600;">'
            '<span style="font-size:18px;">{icon}</span>{label}'
            '</span>',
            color=color,
            icon=icon,
            label=label,
        )

    translation_status_note.short_description = 'Перевод'
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранные объекты недвижимости на английский и тайский (только пустые поля)"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        skipped_count = 0
        
        for property_obj in queryset:
            try:
                translate_property(property_obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода объекта "{property_obj.title}": {e}', level=messages.ERROR)
                skipped_count += 1
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, 
                f'Успешно переведено {translated_count} объектов недвижимости через {service_name.upper()}. '
                f'Пропущено: {skipped_count} (уже переведены или ошибки).')
        else:
            self.message_user(request, 'Не удалось перевести ни одного объекта.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH (только пустые поля)"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранные объекты недвижимости, перезаписывая существующие переводы"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for property_obj in queryset:
            try:
                translate_property(property_obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода объекта "{property_obj.title}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, 
                f'Принудительно переведено {translated_count} объектов недвижимости через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного объекта.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново (перезаписать все переводы)"
    
    def save_model(self, request, obj, form, change):
        if not change:  # Если это новый объект
            # Устанавливаем Кирилла как контактное лицо по умолчанию, если contact_person не указан
            if not obj.contact_person_id:
                try:
                    from apps.core.models import Team
                    default_manager = Team.objects.get(id=2)  # Kirill Dedyugin
                    obj.contact_person = default_manager
                except Team.DoesNotExist:
                    pass  # Если сотрудник не найден, оставляем пустым
        super().save_model(request, obj, form, change)
        if change:
            from apps.arealisting.services.field_ownership import (
                SOURCE_FIELD_LABELS,
                protect_property_manual_changes,
            )

            protected = protect_property_manual_changes(obj, form.changed_data)
            if protected:
                labels = ', '.join(SOURCE_FIELD_LABELS.get(field, field) for field in protected)
                self.message_user(
                    request,
                    f'Ручные изменения защищены от AREALISTING: {labels}.',
                    level=messages.INFO,
                )

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        if not change:
            return
        feature_changed = any(
            formset.model is PropertyFeatureRelation and formset.has_changed()
            for formset in formsets
        )
        if feature_changed:
            from apps.arealisting.services.field_ownership import (
                protect_property_manual_changes,
            )

            if protect_property_manual_changes(form.instance, {'features'}):
                self.message_user(
                    request,
                    'Ручные изменения характеристик защищены от AREALISTING.',
                    level=messages.INFO,
                )
        images_changed = any(
            formset.model is PropertyImage and formset.has_changed()
            for formset in formsets
        )
        if images_changed:
            from apps.arealisting.services.field_ownership import (
                protect_property_manual_changes,
            )

            if protect_property_manual_changes(form.instance, {'images', 'floorplans'}):
                self.message_user(
                    request,
                    'Ручные изменения фотографий и планировок защищены от AREALISTING.',
                    level=messages.INFO,
                )

    def get_queryset(self, request):
        """Переопределяем queryset для отображения количества просмотров"""
        return super().get_queryset(request).select_related('property_type', 'district', 'contact_person')

    def bulk_image_upload_widget(self, obj=None):
        """Виджет для массовой загрузки изображений"""
        if obj and obj.pk:
            from django.urls import reverse
            from django.utils.safestring import mark_safe
            
            upload_url = reverse('admin_bulk_upload_images')
            
            html = f"""
            <div id="bulk-image-upload-section">
                <h3>📸 Массовая загрузка изображений</h3>
                <div id="bulk-upload-area" style="border: 2px dashed #ccc; padding: 20px; text-align: center; margin: 15px 0; background: #f9f9f9;">
                    <input type="file" id="bulk-images-input" multiple accept="image/*" style="display: none;">
                    <div id="upload-prompt" onclick="document.getElementById('bulk-images-input').click();" style="cursor: pointer;">
                        <div style="font-size: 36px; margin-bottom: 10px;">📸</div>
                        <h4>Загрузить несколько изображений сразу</h4>
                        <p>Нажмите здесь или перетащите файлы</p>
                        <p><small>Поддерживаемые форматы: JPG, PNG, GIF (максимум 10MB на файл)</small></p>
                    </div>
                    <div id="selected-images-preview"></div>
                </div>
                <div style="text-align: center; margin: 15px 0;">
                    <button type="button" id="upload-selected-btn" onclick="uploadSelectedImages()" 
                            style="background: #007cba; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer; margin-right: 10px;">
                        🚀 Загрузить выбранные изображения
                    </button>
                    <button type="button" onclick="clearSelectedImages()" 
                            style="background: #666; color: white; border: none; padding: 12px 24px; border-radius: 4px; cursor: pointer;">
                        🗑️ Очистить выбор
                    </button>
                </div>
            </div>

            <div id="bulk-upload-status-modal" style="display: none; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.55); z-index: 9999; align-items: center; justify-content: center;">
                <div style="background: #ffffff; padding: 25px 35px; border-radius: 12px; width: 420px; max-width: 90%; text-align: center; box-shadow: 0 20px 45px rgba(0,0,0,0.25);">
                    <div class="bulk-upload-spinner" style="width: 48px; height: 48px; border-radius: 50%; border: 5px solid #e5e7eb; border-top-color: #007cba; margin: 0 auto 20px; animation: bulk-spin 0.9s linear infinite;"></div>
                    <h4 style="margin-bottom: 10px; font-size: 20px; color: #111827;">Идёт загрузка изображений</h4>
                    <p id="upload-status-text" style="margin: 0; color: #374151; font-size: 15px;">Передаём файлы на сервер...</p>
                    <p id="upload-status-hint" style="margin-top: 10px; font-size: 13px; color: #6b7280;">Пожалуйста, не закрывайте страницу — изображения автоматически конвертируются в WebP.</p>
                </div>
            </div>

            <style>
                @keyframes bulk-spin {{
                    0% {{ transform: rotate(0deg); }}
                    100% {{ transform: rotate(360deg); }}
                }}
            </style>
            
            <script>
                let selectedFiles = [];
                const uploadArea = document.getElementById('bulk-upload-area');
                const fileInput = document.getElementById('bulk-images-input');
                const previewArea = document.getElementById('selected-images-preview');
                const uploadBtn = document.getElementById('upload-selected-btn');
                const statusModal = document.getElementById('bulk-upload-status-modal');
                const statusTextEl = document.getElementById('upload-status-text');
                const statusHintEl = document.getElementById('upload-status-hint');
                
                // Drag & Drop функциональность
                uploadArea.addEventListener('dragover', function(e) {{
                    e.preventDefault();
                    this.style.borderColor = '#007cba';
                    this.style.backgroundColor = '#f0f8ff';
                }});
                
                uploadArea.addEventListener('dragleave', function(e) {{
                    e.preventDefault();
                    this.style.borderColor = '#ccc';
                    this.style.backgroundColor = '#f9f9f9';
                }});
                
                uploadArea.addEventListener('drop', function(e) {{
                    e.preventDefault();
                    this.style.borderColor = '#ccc';
                    this.style.backgroundColor = '#f9f9f9';
                    const files = Array.from(e.dataTransfer.files).filter(file => file.type.startsWith('image/'));
                    handleFileSelection(files);
                }});
                
                // Обработка выбора файлов
                fileInput.addEventListener('change', function(e) {{
                    const files = Array.from(e.target.files);
                    handleFileSelection(files);
                }});
                
                function handleFileSelection(files) {{
                    selectedFiles = files;
                    displaySelectedImages();
                    uploadBtn.style.display = files.length > 0 ? 'inline-block' : 'none';
                }}
                
                function displaySelectedImages() {{
                    previewArea.innerHTML = '';
                    
                    if (selectedFiles.length > 0) {{
                        const header = document.createElement('h4');
                        header.textContent = `Выбрано изображений: ${{selectedFiles.length}}`;
                        header.style.color = '#007cba';
                        previewArea.appendChild(header);
                        
                        const imageGrid = document.createElement('div');
                        imageGrid.style.display = 'grid';
                        imageGrid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(120px, 1fr))';
                        imageGrid.style.gap = '10px';
                        imageGrid.style.marginTop = '15px';
                        
                        selectedFiles.forEach((file, index) => {{
                            const reader = new FileReader();
                            reader.onload = function(e) {{
                                const imageItem = document.createElement('div');
                                imageItem.style.border = '1px solid #ddd';
                                imageItem.style.borderRadius = '4px';
                                imageItem.style.padding = '8px';
                                imageItem.style.background = 'white';
                                imageItem.style.textAlign = 'center';
                                imageItem.innerHTML = `
                                    <img src="${{e.target.result}}" style="width: 100%; height: 80px; object-fit: cover; border-radius: 4px;">
                                    <div style="font-size: 10px; margin-top: 5px; word-break: break-all;">
                                        <strong>${{file.name.substring(0, 15)}}${{file.name.length > 15 ? '...' : ''}}</strong><br>
                                        ${{(file.size / 1024 / 1024).toFixed(1)}} MB
                                    </div>
                                    <button onclick="removeImage(${{index}})" 
                                            style="background: #dc3545; color: white; border: none; border-radius: 50%; width: 20px; height: 20px; cursor: pointer; margin-top: 5px;">×</button>
                                `;
                                imageGrid.appendChild(imageItem);
                            }};
                            reader.readAsDataURL(file);
                        }});
                        
                        previewArea.appendChild(imageGrid);
                    }}
                }}
                
                function removeImage(index) {{
                    selectedFiles.splice(index, 1);
                    displaySelectedImages();
                    uploadBtn.style.display = selectedFiles.length > 0 ? 'inline-block' : 'none';
                }}
                
                function clearSelectedImages() {{
                    selectedFiles = [];
                    fileInput.value = '';
                    displaySelectedImages();
                    uploadBtn.style.display = 'none';
                }}

                function showUploadStatus(mainText, hintText) {{
                    if (statusTextEl && mainText) {{
                        statusTextEl.textContent = mainText;
                    }}
                    if (statusHintEl) {{
                        statusHintEl.textContent = hintText || 'Пожалуйста, не закрывайте страницу — изображения автоматически конвертируются в WebP.';
                    }}
                    if (statusModal) {{
                        statusModal.style.display = 'flex';
                    }}
                }}

                function hideUploadStatus() {{
                    if (statusModal) {{
                        statusModal.style.display = 'none';
                    }}
                }}
                
                async function uploadSelectedImages() {{
                    if (selectedFiles.length === 0) {{
                        alert('Пожалуйста, выберите изображения для загрузки');
                        return;
                    }}
                    
                    const files = [...selectedFiles];
                    const failedFiles = [];
                    const errors = [];
                    let uploadedCount = 0;
                    showUploadStatus(
                        `Загружаем 1 из ${{files.length}}...`,
                        'Пожалуйста, не закрывайте страницу до завершения загрузки.'
                    );
                    uploadBtn.disabled = true;

                    for (const [index, file] of files.entries()) {{
                        statusTextEl.textContent = `Загружаем ${{index + 1}} из ${{files.length}}: ${{file.name}}`;
                        const formData = new FormData();
                        formData.append('property_id', '{obj.pk}');
                        formData.append('images', file);
                        try {{
                            const response = await fetch('{upload_url}', {{
                                method: 'POST',
                                body: formData,
                                headers: {{
                                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                                }}
                            }});
                            const contentType = response.headers.get('content-type') || '';
                            if (!contentType.includes('application/json')) {{
                                throw new Error(`Сервер вернул HTTP ${{response.status}} вместо ответа загрузчика.`);
                            }}
                            const data = await response.json();
                            if (!response.ok || !data.success || !data.images?.length) {{
                                throw new Error(data.errors?.join('; ') || data.message || `HTTP ${{response.status}}`);
                            }}
                            uploadedCount += data.images.length;
                        }} catch (error) {{
                            failedFiles.push(file);
                            errors.push(`${{file.name}}: ${{error.message}}`);
                            console.error('Error uploading image:', file.name, error);
                        }}
                    }}

                    hideUploadStatus();
                    uploadBtn.disabled = false;
                    if (failedFiles.length) {{
                        selectedFiles = failedFiles;
                        displaySelectedImages();
                        alert(`Загружено: ${{uploadedCount}} из ${{files.length}}. Не удалось загрузить:\n${{errors.join(String.fromCharCode(10))}}\nПроверьте галерею перед повторной отправкой: при таймауте файл мог сохраниться.`);
                    }} else {{
                        alert(`Успешно загружено ${{uploadedCount}} изображений!`);
                        clearSelectedImages();
                        location.reload();
                    }}
                }}
            </script>
            """
            return mark_safe(html)
        else:
            return mark_safe('<p><em>Сохраните объект недвижимости, чтобы загружать изображения.</em></p>')
    
    bulk_image_upload_widget.short_description = 'Массовая загрузка изображений'

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'legacy_id',
                'complex_name',
                'title',
                'slug',
                'district',
                'property_type',
                'deal_type',
                'status',
                'build_status',
                'is_featured',
                'featured_priority',
                'is_active'
            )
        }),
        ('Описание', {
            'fields': ('description', 'short_description', 'special_offer')
        }),
        ('Переводы специального предложения', {
            'fields': ('special_offer_en', 'special_offer_th'),
            'classes': ('collapse',),
        }),
        ('Локация', {
            'fields': ('location', 'address', 'latitude', 'longitude')
        }),
        ('Характеристики', {
            'fields': ('bedrooms', 'bathrooms', 'area_total', 'area_living', 'area_land', 'floor', 'floors_total')
        }),
        ('Цены', {
            'fields': ('price_sale_thb', 'price_sale_usd', 'price_sale_rub', 'price_rent_monthly')
        }),
        ('Дополнительно', {
            'fields': ('developer', 'contact_person', 'year_built', 'furnished', 'pool', 'parking', 'security', 'gym')
        }),
        ('SEO настройки (опционально)', {
            'fields': (
                ('custom_title_ru', 'custom_title_en', 'custom_title_th'),
                ('custom_description_ru', 'custom_description_en', 'custom_description_th'),
                ('custom_keywords_ru', 'custom_keywords_en', 'custom_keywords_th'),
            ),
            'classes': ('collapse',),
            'description': 'Оставьте поля пустыми для автоматической генерации SEO данных на основе шаблонов'
        }),
    )

    # Добавляем readonly поля для отображения кастомного виджета
    def get_readonly_fields(self, request, obj=None):
        """Добавляем readonly поле только если объект уже существует"""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.pk:
            readonly_fields.append('bulk_image_upload_widget')
        return readonly_fields
    
    def get_fieldsets(self, request, obj=None):
        """Добавляем секцию массовой загрузки изображений только при редактировании существующего объекта"""
        fieldsets = list(super().get_fieldsets(request, obj))
        
        # Добавляем секцию массовой загрузки только если объект уже существует
        if obj and obj.pk:
            fieldsets.insert(1, (
                'Синхронизация AREALISTING', {
                    'fields': ('arealisting_sync_note',),
                }
            ))
            fieldsets.insert(-1, (
                'Массовая загрузка изображений', {
                    'fields': ('bulk_image_upload_widget',),
                    'description': 'Загрузите несколько изображений одновременно'
                }
            ))
        
        return fieldsets


@admin.register(PropertyType)
class PropertyTypeAdmin(BaseAdminWithRequiredFields):
    list_display = ('name', 'name_display', 'icon')
    actions = ['auto_translate', 'force_retranslate']
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранные типы недвижимости"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_type(obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода типа "{obj.name_display}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Успешно переведено {translated_count} типов недвижимости через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного типа.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранные типы недвижимости"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_type(obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода типа "{obj.name_display}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Принудительно переведено {translated_count} типов недвижимости через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного типа.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново"


@admin.register(Developer)
class DeveloperAdmin(BaseAdminWithRequiredFields):
    list_display = ('name', 'website')
    prepopulated_fields = {'slug': ('name',)}
    actions = ['auto_translate', 'force_retranslate']
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранных застройщиков"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_developer(obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода застройщика "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Успешно переведено {translated_count} застройщиков через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного застройщика.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранных застройщиков"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_developer(obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода застройщика "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Принудительно переведено {translated_count} застройщиков через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одного застройщика.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново"


@admin.register(PropertyFeature)
class PropertyFeatureAdmin(BaseAdminWithRequiredFields):
    list_display = ('name', 'icon')
    actions = ['auto_translate', 'force_retranslate']
    
    def auto_translate(self, request, queryset):
        """Автоматически переводит выбранные характеристики"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_feature(obj, force_retranslate=False)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода характеристики "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Успешно переведено {translated_count} характеристик через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одной характеристики.', level=messages.WARNING)
    
    auto_translate.short_description = "🌐 Перевести на EN и TH"
    
    def force_retranslate(self, request, queryset):
        """Принудительно переводит выбранные характеристики"""
        from apps.core.services import translation_service
        
        if not translation_service.is_configured():
            self.message_user(request, 
                'API перевода не настроен. Пожалуйста, добавьте YANDEX_TRANSLATE_API_KEY и YANDEX_TRANSLATE_FOLDER_ID в настройки.', 
                level=messages.ERROR)
            return
        
        translated_count = 0
        
        for obj in queryset:
            try:
                translate_property_feature(obj, force_retranslate=True)
                translated_count += 1
            except Exception as e:
                self.message_user(request, f'Ошибка перевода характеристики "{obj.name}": {e}', level=messages.ERROR)
        
        if translated_count > 0:
            service_name = translation_service.get_available_service()
            self.message_user(request, f'Принудительно переведено {translated_count} характеристик через {service_name.upper()}.')
        else:
            self.message_user(request, 'Не удалось перевести ни одной характеристики.', level=messages.WARNING)
    
    force_retranslate.short_description = "🔄 Перевести заново"
