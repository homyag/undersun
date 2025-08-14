from django import forms
from django.utils.translation import gettext_lazy as _
from .models import ImportFile, PropertyImportMapping


class ImportFileForm(forms.ModelForm):
    """Форма для загрузки файла импорта"""
    
    class Meta:
        model = ImportFile
        fields = ['file', 'import_type']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.xlsx,.xls',
                'id': 'import-file-input'
            }),
            'import_type': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        self.fields['file'].help_text = _(
            'Поддерживаемые форматы: .xlsx, .xls. Максимальный размер: 10MB'
        )
        self.fields['import_type'].help_text = _(
            'Выберите тип операции импорта'
        )
        
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            # Проверяем размер файла (10MB)
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError(
                    _('Размер файла не должен превышать 10MB')
                )
                
            # Проверяем расширение файла
            if not file.name.lower().endswith(('.xlsx', '.xls')):
                raise forms.ValidationError(
                    _('Поддерживаются только файлы Excel (.xlsx, .xls)')
                )
                
        return file
        
    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.name = self.cleaned_data['file'].name
        if self.user:
            instance.uploaded_by = self.user
        if commit:
            instance.save()
        return instance


class MappingForm(forms.ModelForm):
    """Форма для создания и редактирования маппинга полей"""
    
    class Meta:
        model = PropertyImportMapping
        fields = ['name', 'description', 'is_default', 'header_row', 'data_start_row', 'field_mapping']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'header_row': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'data_start_row': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'field_mapping': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 10,
                'placeholder': '{"A": "legacy_id", "B": "title", "C": "price_sale_usd"}'
            })
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.fields['field_mapping'].help_text = _(
            'JSON маппинг в формате: {"Excel_колонка": "поле_модели"}. '
            'Например: {"A": "legacy_id", "B": "title", "C": "price_sale_usd"}'
        )
        
    def clean_field_mapping(self):
        import json
        mapping = self.cleaned_data.get('field_mapping')
        
        if mapping:
            try:
                # Проверяем, что это валидный JSON
                parsed_mapping = json.loads(mapping) if isinstance(mapping, str) else mapping
                
                # Проверяем, что все значения являются допустимыми полями
                valid_fields = [field[0] for field in PropertyImportMapping.PROPERTY_FIELDS]
                
                for excel_col, model_field in parsed_mapping.items():
                    if model_field not in valid_fields:
                        raise forms.ValidationError(
                            _('Недопустимое поле модели: {}. Допустимые поля: {}').format(
                                model_field, ', '.join(valid_fields)
                            )
                        )
                        
                return parsed_mapping
                
            except json.JSONDecodeError:
                raise forms.ValidationError(
                    _('Неправильный формат JSON. Используйте формат: {"A": "legacy_id", "B": "title"}')
                )
                
        return mapping


class ImportPreviewForm(forms.Form):
    """Форма для предварительного просмотра данных импорта"""
    
    mapping = forms.ModelChoiceField(
        queryset=PropertyImportMapping.objects.all(),
        empty_label=_('-- Выберите маппинг --'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Маппинг полей')
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Устанавливаем маппинг по умолчанию
        default_mapping = PropertyImportMapping.get_default()
        if default_mapping:
            self.fields['mapping'].initial = default_mapping
            
        self.fields['mapping'].help_text = _(
            'Выберите схему соответствия колонок Excel полям объектов недвижимости'
        )


class BulkActionForm(forms.Form):
    """Форма для массовых действий с импортированными данными"""
    
    ACTION_CHOICES = [
        ('', _('-- Выберите действие --')),
        ('process', _('Обработать импорт')),
        ('delete', _('Удалить')),
        ('reprocess', _('Переобработать')),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label=_('Действие')
    )
    
    selected_files = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def clean_selected_files(self):
        selected = self.cleaned_data.get('selected_files', '')
        if selected:
            try:
                file_ids = [int(id_str) for id_str in selected.split(',') if id_str.strip()]
                return file_ids
            except ValueError:
                raise forms.ValidationError(_('Неправильный формат выбранных файлов'))
        return []