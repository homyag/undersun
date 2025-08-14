import openpyxl
import pandas as pd
import json
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from typing import Dict, List, Any, Optional, Tuple
from apps.properties.models import Property, PropertyType, Developer, Agent
from apps.locations.models import District, Location
from .models import ImportFile, ImportLog, PropertyImportMapping


class ExcelParser:
    """Парсер Excel файлов с конвертацией в JSON"""
    
    def __init__(self, file_path: str, mapping: PropertyImportMapping = None):
        self.file_path = file_path
        self.mapping = mapping or PropertyImportMapping.get_default()
        self.workbook = None
        self.worksheet = None
        
    def parse_file(self) -> Dict[str, Any]:
        """Парсит Excel файл и возвращает структурированные данные"""
        try:
            self.workbook = openpyxl.load_workbook(self.file_path, data_only=True)
            self.worksheet = self.workbook.active
            
            # Получаем заголовки
            headers = self._extract_headers()
            
            # Парсим данные
            data_rows = self._extract_data_rows()
            
            # Конвертируем в JSON структуру
            json_data = self._convert_to_json(headers, data_rows)
            
            return {
                'success': True,
                'data': json_data,
                'total_rows': len(data_rows),
                'headers': headers,
                'errors': []
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': [],
                'total_rows': 0,
                'headers': [],
                'errors': [f"Ошибка парсинга файла: {str(e)}"]
            }
        finally:
            if self.workbook:
                self.workbook.close()
    
    def _extract_headers(self) -> Dict[str, str]:
        """Извлекает заголовки из указанной строки"""
        headers = {}
        if not self.mapping:
            return headers
            
        header_row = self.mapping.header_row
        for cell in self.worksheet[header_row]:
            if cell.value:
                column_letter = cell.column_letter
                headers[column_letter] = str(cell.value).strip()
                
        return headers
    
    def _extract_data_rows(self) -> List[Dict[str, Any]]:
        """Извлекает строки данных"""
        data_rows = []
        if not self.mapping:
            return data_rows
            
        start_row = self.mapping.data_start_row
        max_row = self.worksheet.max_row
        
        for row_num in range(start_row, max_row + 1):
            row_data = {}
            has_data = False
            
            for cell in self.worksheet[row_num]:
                column_letter = cell.column_letter
                if cell.value is not None:
                    row_data[column_letter] = cell.value
                    has_data = True
                else:
                    row_data[column_letter] = None
            
            if has_data:
                row_data['_row_number'] = row_num
                data_rows.append(row_data)
                
        return data_rows
    
    def _convert_to_json(self, headers: Dict[str, str], data_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Конвертирует данные в JSON используя маппинг полей"""
        json_data = []
        
        if not self.mapping or not self.mapping.field_mapping:
            return json_data
            
        for row_data in data_rows:
            json_row = {'_row_number': row_data.get('_row_number')}
            
            for excel_column, property_field in self.mapping.field_mapping.items():
                value = row_data.get(excel_column)
                
                # Преобразуем значение в подходящий тип
                converted_value = self._convert_value(value, property_field)
                json_row[property_field] = converted_value
                
            json_data.append(json_row)
            
        return json_data
    
    def _convert_value(self, value: Any, field_name: str) -> Any:
        """Конвертирует значение в подходящий тип для поля"""
        if value is None or value == '':
            return None
            
        # Числовые поля
        numeric_fields = [
            'price_sale_usd', 'price_sale_thb', 'price_sale_rub',
            'price_rent_monthly', 'price_rent_monthly_thb', 'price_rent_monthly_rub',
            'area_total', 'area_living', 'area_land', 'pool_area',
            'bedrooms', 'bathrooms', 'floor', 'floors_total',
            'year_built', 'distance_to_beach', 'distance_to_airport', 'distance_to_school',
            'double_beds', 'single_beds', 'sofa_beds'
        ]
        
        # Decimal поля (цены, площади)
        decimal_fields = [
            'price_sale_usd', 'price_sale_thb', 'price_sale_rub',
            'price_rent_monthly', 'price_rent_monthly_thb', 'price_rent_monthly_rub',
            'area_total', 'area_living', 'area_land', 'pool_area',
            'latitude', 'longitude'
        ]
        
        # Boolean поля
        boolean_fields = [
            'furnished', 'pool', 'parking', 'security', 'gym', 'is_urgent_sale'
        ]
        
        try:
            if field_name in boolean_fields:
                if isinstance(value, bool):
                    return value
                if isinstance(value, str):
                    return value.lower() in ['true', 'да', 'yes', '1', '+']
                return bool(value)
                
            elif field_name in decimal_fields:
                if isinstance(value, (int, float)):
                    return Decimal(str(value))
                elif isinstance(value, str):
                    # Удаляем пробелы и запятые
                    clean_value = value.replace(' ', '').replace(',', '.')
                    return Decimal(clean_value)
                    
            elif field_name in numeric_fields:
                if isinstance(value, (int, float)):
                    return int(value)
                elif isinstance(value, str):
                    return int(float(value.replace(' ', '').replace(',', '.')))
                    
            else:
                # Строковые поля
                return str(value).strip() if value else None
                
        except (ValueError, InvalidOperation, TypeError):
            return str(value) if value else None


class DataValidator:
    """Валидатор данных из Excel"""
    
    def __init__(self, import_file: ImportFile):
        self.import_file = import_file
        self.errors = []
        
    def validate_data(self, json_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Валидирует данные и возвращает результат"""
        valid_data = []
        
        for row_data in json_data:
            row_number = row_data.get('_row_number', 'Unknown')
            row_errors = []
            
            # Валидируем каждое поле
            validated_row = self._validate_row(row_data, row_errors)
            
            if row_errors:
                # Записываем ошибки
                for error in row_errors:
                    self.import_file.add_validation_error(
                        row_number, error['field'], error['message']
                    )
                    
                    ImportLog.objects.create(
                        import_file=self.import_file,
                        level='error',
                        message=f"Ошибка валидации в строке {row_number}: {error['message']}",
                        row_number=row_number,
                        details={'field': error['field'], 'value': error.get('value')}
                    )
            else:
                valid_data.append(validated_row)
                
        return {
            'valid_data': valid_data,
            'total_errors': len(self.errors),
            'errors': self.errors
        }
    
    def _validate_row(self, row_data: Dict[str, Any], row_errors: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Валидирует одну строку данных"""
        validated_row = {}
        row_number = row_data.get('_row_number')
        
        # Копируем номер строки
        validated_row['_row_number'] = row_number
        
        for field_name, value in row_data.items():
            if field_name == '_row_number':
                continue
                
            try:
                validated_value = self._validate_field(field_name, value)
                validated_row[field_name] = validated_value
            except ValidationError as e:
                row_errors.append({
                    'field': field_name,
                    'value': value,
                    'message': str(e)
                })
                
        return validated_row
    
    def _validate_field(self, field_name: str, value: Any) -> Any:
        """Валидирует отдельное поле"""
        if value is None:
            return None
            
        # Специфическая валидация для разных полей
        if field_name == 'legacy_id':
            if not value:
                raise ValidationError("ID объекта не может быть пустым")
            return str(value)
            
        elif field_name in ['price_sale_usd', 'price_sale_thb', 'price_sale_rub',
                           'price_rent_monthly', 'price_rent_monthly_thb', 'price_rent_monthly_rub']:
            if isinstance(value, (int, float, Decimal)) and value < 0:
                raise ValidationError(f"Цена не может быть отрицательной: {value}")
            return value
            
        elif field_name in ['area_total', 'area_living', 'area_land']:
            if isinstance(value, (int, float, Decimal)) and value <= 0:
                raise ValidationError(f"Площадь должна быть положительной: {value}")
            return value
            
        elif field_name in ['bedrooms', 'bathrooms']:
            if isinstance(value, int) and (value < 0 or value > 20):
                raise ValidationError(f"Неправильное количество комнат: {value}")
            return value
            
        elif field_name == 'status':
            valid_statuses = ['available', 'reserved', 'sold', 'rented']
            if value and str(value).lower() not in valid_statuses:
                raise ValidationError(f"Неправильный статус: {value}. Допустимы: {valid_statuses}")
            return str(value).lower() if value else None
            
        elif field_name == 'deal_type':
            valid_types = ['sale', 'rent', 'both']
            if value and str(value).lower() not in valid_types:
                raise ValidationError(f"Неправильный тип сделки: {value}. Допустимы: {valid_types}")
            return str(value).lower() if value else None
            
        elif field_name in ['latitude', 'longitude']:
            if isinstance(value, (int, float, Decimal)):
                if field_name == 'latitude' and not (-90 <= float(value) <= 90):
                    raise ValidationError(f"Широта должна быть между -90 и 90: {value}")
                elif field_name == 'longitude' and not (-180 <= float(value) <= 180):
                    raise ValidationError(f"Долгота должна быть между -180 и 180: {value}")
            return value
            
        return value


class PropertyUpdater:
    """Обновляет свойства недвижимости из валидированных данных"""
    
    def __init__(self, import_file: ImportFile):
        self.import_file = import_file
        
    def update_properties(self, valid_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Обновляет объекты недвижимости"""
        updated_count = 0
        created_count = 0
        error_count = 0
        
        with transaction.atomic():
            for row_data in valid_data:
                try:
                    result = self._update_single_property(row_data)
                    if result['created']:
                        created_count += 1
                    else:
                        updated_count += 1
                        
                    ImportLog.objects.create(
                        import_file=self.import_file,
                        level='success',
                        message=f"{'Создан' if result['created'] else 'Обновлен'} объект: {result['property'].title}",
                        row_number=row_data.get('_row_number'),
                        details={'property_id': result['property'].id}
                    )
                    
                except Exception as e:
                    error_count += 1
                    ImportLog.objects.create(
                        import_file=self.import_file,
                        level='error',
                        message=f"Ошибка обновления объекта: {str(e)}",
                        row_number=row_data.get('_row_number'),
                        details={'error': str(e), 'data': row_data}
                    )
                    
        return {
            'updated_count': updated_count,
            'created_count': created_count,
            'error_count': error_count,
            'total_processed': updated_count + created_count
        }
    
    def _update_single_property(self, row_data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет один объект недвижимости"""
        legacy_id = row_data.get('legacy_id')
        
        if not legacy_id:
            raise ValueError("Не указан ID объекта для обновления")
            
        # Ищем существующий объект
        property_obj = None
        created = False
        
        try:
            property_obj = Property.objects.get(legacy_id=legacy_id)
        except Property.DoesNotExist:
            if self.import_file.import_type == 'property_create':
                # Создаем новый объект
                property_obj = Property(legacy_id=legacy_id)
                created = True
            else:
                raise ValueError(f"Объект с ID {legacy_id} не найден")
                
        # Обновляем поля
        for field_name, value in row_data.items():
            if field_name in ['_row_number'] or value is None:
                continue
                
            if hasattr(property_obj, field_name):
                setattr(property_obj, field_name, value)
                
        # Сохраняем объект
        property_obj.save()
        
        return {
            'property': property_obj,
            'created': created
        }


class ImportProcessor:
    """Основной процессор импорта данных"""
    
    def __init__(self, import_file: ImportFile):
        self.import_file = import_file
        
    def process_import(self) -> Dict[str, Any]:
        """Обрабатывает импорт файла"""
        try:
            # Обновляем статус
            self.import_file.status = 'processing'
            self.import_file.started_at = timezone.now()
            self.import_file.save()
            
            # Парсим файл
            parser = ExcelParser(self.import_file.file.path, self.import_file.mapping)
            parse_result = parser.parse_file()
            
            if not parse_result['success']:
                self.import_file.status = 'failed'
                self.import_file.validation_errors = parse_result['errors']
                self.import_file.save()
                return parse_result
                
            # Сохраняем распарсенные данные
            self.import_file.parsed_data = parse_result['data']
            self.import_file.total_rows = parse_result['total_rows']
            self.import_file.save()
            
            # Валидируем данные
            validator = DataValidator(self.import_file)
            validation_result = validator.validate_data(parse_result['data'])
            
            # Обновляем объекты недвижимости
            updater = PropertyUpdater(self.import_file)
            update_result = updater.update_properties(validation_result['valid_data'])
            
            # Обновляем статистику
            self.import_file.processed_rows = len(parse_result['data'])
            self.import_file.successful_rows = update_result['total_processed']
            self.import_file.failed_rows = update_result['error_count'] + validation_result['total_errors']
            self.import_file.status = 'completed'
            self.import_file.completed_at = timezone.now()
            self.import_file.save()
            
            return {
                'success': True,
                'message': 'Импорт завершен успешно',
                'statistics': {
                    'total_rows': self.import_file.total_rows,
                    'processed_rows': self.import_file.processed_rows,
                    'successful_rows': self.import_file.successful_rows,
                    'failed_rows': self.import_file.failed_rows,
                    'success_rate': self.import_file.success_rate,
                    'updated_count': update_result['updated_count'],
                    'created_count': update_result['created_count']
                }
            }
            
        except Exception as e:
            # В случае критической ошибки
            self.import_file.status = 'failed'
            self.import_file.completed_at = timezone.now()
            self.import_file.save()
            
            ImportLog.objects.create(
                import_file=self.import_file,
                level='error',
                message=f"Критическая ошибка импорта: {str(e)}",
                details={'error': str(e)}
            )
            
            return {
                'success': False,
                'message': f'Критическая ошибка импорта: {str(e)}',
                'error': str(e)
            }