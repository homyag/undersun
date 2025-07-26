# Отчет нормализации legacy_id и проверки фотографий

## Общая статистика

- **Объектов в маппинге**: 769
- **Объектов в Django**: 748
- **Нормализованных legacy_id**: 702
- **Совпадений после нормализации**: 474
- **Процент совпадений**: 63.4%

## Статистика фотографий

- **Объектов с фото**: 765
- **Всего файлов фото**: 7733
- **Существующих файлов**: 12
- **Отсутствующих файлов**: 7721
- **Отсутствующих папок**: 732
- **Процент существующих фото**: 0.2%

## Примеры совпадений после нормализации

1. **CN1-1BR-38M**: 1 Bedroom Apartment in Bang Tao, Phuket in Above E...
   Mapping ID: 327, Django ID: 5840

2. **CN1-3BR-138M**: 3 Bedroom Apartment in Bang Tao, Phuket in Above E...
   Mapping ID: 331, Django ID: 5844

3. **CN1-2BR-47M**: 2 Bedroom Apartment in Bang Tao, Phuket in Above E...
   Mapping ID: 332, Django ID: 5845

4. **CN4-3BR-227M**: 3 Bedroom Penthouse with private roof terrace in P...
   Mapping ID: 334, Django ID: 5846

5. **CN4-2BR-273M**: Penthouse with terrace and plunge pool in Patong, ...
   Mapping ID: 335, Django ID: 5847

6. **CN11-1BR-36M**: 1 Bedroom suite in a resort condominium near Layan...
   Mapping ID: 336, Django ID: 5848

7. **CN11-1BR-25M**: Deluxe studio in a resort condominium near Layan B...
   Mapping ID: 337, Django ID: 5849

8. **CN13-1BR-74M**: 1 bedroom apartment in an eco-friendly apartment h...
   Mapping ID: 338, Django ID: 5850

9. **CN13-1BR-36M**: Studio in an eco-friendly apartment hotel near Ban...
   Mapping ID: 339, Django ID: 5851

10. **CN3-1BR-38M**: Studio on Kamala Beach, Phuket in Platinum Bay Con...
   Mapping ID: 355, Django ID: 5865

11. **CN3-1BR-37M**: 1 Bedroom Apartment with Private Balcony by Kamala...
   Mapping ID: 356, Django ID: 5866

12. **CN3-1BR-35M**: 1 Bedroom Apartment with Private Outdoor Pool on K...
   Mapping ID: 357, Django ID: 5867

13. **VN20-5BR-445M**: Luxury 5 Bedroom Villa near the Lagoon, Phuket at ...
   Mapping ID: 358, Django ID: 5868

14. **VN3-4BR-453M**: Luxury 2-storey villa in Chalong district, Phuket ...
   Mapping ID: 359, Django ID: 5869

15. **VN3-4BR-700M**: Luxury 3-storey villa with sea view in Chalong dis...
   Mapping ID: 360, Django ID: 5870

16. **VN1-3BR-351M**: Landscape two-storey hillside villa in Thalang dis...
   Mapping ID: 368, Django ID: 5874

17. **undefined-0BR-0M**: Land plot with sea view in Rawai, Phuket...
   Mapping ID: 370, Django ID: 5876

18. **VN50-3BR-479M**: Luxury villa with pool in Rawai, Phuket in VIP Gal...
   Mapping ID: 381, Django ID: 5882

19. **VN18-3BR-295M**: Premium villa 30 meters from Rawai Beach, Phuket a...
   Mapping ID: 382, Django ID: 5883

20. **CN48-1BR-52M**: One bedroom apartment in a deluxe condominium in R...
   Mapping ID: 385, Django ID: 5886

## Проблемы с фотографиями

### 1. Landing Page...
- **Папка**: Landing_Page
- **Папка существует**: False
- **Всего файлов**: 23
- **Существует**: 0
- **Отсутствует**: 23
- **Примеры отсутствующих**: landing-page.jpg, landing-page-about-01.jpg, landing-page-about-02.jpg, landing-page-living-room-01.jpg, landing-page-living-room-02.jpg

### 2. Сommercial real estate...
- **Папка**: Сommercial_real_estate
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: 124-online-store.svg

### 3. Selling a land...
- **Папка**: Selling_a_land
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: 010-houses.svg

### 4. 2-story townhouse near Phuket Town...
- **Папка**: 2-story_townhouse_near_Phuket_
- **Папка существует**: False
- **Всего файлов**: 6
- **Существует**: 0
- **Отсутствует**: 6
- **Примеры отсутствующих**: Bangtao.jpg, IMG-20231106-WA0022.jpg, IMG-20231106-WA0023.jpg, IMG-20231106-WA0024.jpg, IMG-20231106-WA0027.jpg

### 5. 1 Bedroom Apartment in Bang Tao, Phuket in Above E...
- **Папка**: CN1
- **Папка существует**: False
- **Всего файлов**: 7
- **Существует**: 0
- **Отсутствует**: 7
- **Примеры отсутствующих**: Elements/U_38_-_1.jpg, Elements/1_Bedroom_38_sqm.png, Elements/ABE-0.jpg, Elements/ABE-11.jpg, Elements/ABE-9.jpg

### 6. 1 Bedroom Condo in Kamala Beach...
- **Папка**: 1_Bedroom_Condo_in_Kamala_Beac
- **Папка существует**: False
- **Всего файлов**: 10
- **Существует**: 0
- **Отсутствует**: 10
- **Примеры отсутствующих**: photo1678884516_3.jpeg, Fantasea/14-1024x768.jpg, Fantasea/1a1.png, Fantasea/2023-03-20_112201.jpg, Fantasea/2023-03-20_112232.jpg

### 7. 2 Bedroom Condo in Kamala Beach...
- **Папка**: 2_Bedroom_Condo_in_Kamala_Beac
- **Папка существует**: False
- **Всего файлов**: 10
- **Существует**: 0
- **Отсутствует**: 10
- **Примеры отсутствующих**: photo1678884516_3.jpeg, Fantasea/14-1024x768.jpg, Fantasea/2.png, Fantasea/2023-03-20_112201.jpg, Fantasea/2023-03-20_112232.jpg

### 8. 1 Bedroom Apartment on Kamala Beach, Phuket in Fan...
- **Папка**: CN7
- **Папка существует**: False
- **Всего файлов**: 10
- **Существует**: 0
- **Отсутствует**: 10
- **Примеры отсутствующих**: photo1678884516_4.jpeg, Fantasea/12.png, Fantasea/14-1024x768.jpg, Fantasea/2023-03-20_112201.jpg, Fantasea/2023-03-20_112232.jpg

### 9. 3 Bedroom Apartment in Bang Tao, Phuket in Above E...
- **Папка**: CN1
- **Папка существует**: False
- **Всего файлов**: 9
- **Существует**: 0
- **Отсутствует**: 9
- **Примеры отсутствующих**: Elements/U47-01.jpg, Elements/3_Bedroom_138_sqm_1.jpg, Elements/ABE-0.jpg, Elements/ABE-11.jpg, Elements/ABE-9.jpg

### 10. 2 Bedroom Apartment in Bang Tao, Phuket in Above E...
- **Папка**: CN1
- **Папка существует**: False
- **Всего файлов**: 8
- **Существует**: 0
- **Отсутствует**: 8
- **Примеры отсутствующих**: Elements/U_76_-5.jpg, Elements/1_Bedroom_Corner_38_sqm.jpg, Elements/ABE-0.jpg, Elements/ABE-11.jpg, Elements/ABE-9.jpg

### 11. 3 Bedroom Penthouse with private roof terrace in P...
- **Папка**: CN4
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: 3_br_ph_3.jpg

### 12. Penthouse with terrace and plunge pool in Patong, ...
- **Папка**: CN4
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: duplex_2br_3.jpg

### 13. 1 Bedroom suite in a resort condominium near Layan...
- **Папка**: CN11
- **Папка существует**: False
- **Всего файлов**: 3
- **Существует**: 0
- **Отсутствует**: 3
- **Примеры отсутствующих**: Laya_Wanda_Vista/1.jpg, Laya_Wanda_Vista/3.jpg, Laya_Wanda_Vista/4.jpg

### 14. Deluxe studio in a resort condominium near Layan B...
- **Папка**: CN11
- **Папка существует**: False
- **Всего файлов**: 3
- **Существует**: 0
- **Отсутствует**: 3
- **Примеры отсутствующих**: Laya_Wanda_Vista/1.jpg, Laya_Wanda_Vista/3.jpg, Laya_Wanda_Vista/4.jpg

### 15. 1 bedroom apartment in an eco-friendly apartment h...
- **Папка**: CN13
- **Папка существует**: False
- **Всего файлов**: 10
- **Существует**: 0
- **Отсутствует**: 10
- **Примеры отсутствующих**: Layan_Green/TYPE_B_standard_1-bedroom_-_living_room_zone_1.jpg, Layan_Green/Building_Hjpg.jpg, Layan_Green/Drone_photo_-_1_and_2_phasesjpg.jpg, Layan_Green/Main_pool_and_bridgejpg.jpg, Layan_Green/TYPE_B_standard_1-bedroom_-_bedroom.jpg

### 16. Studio in an eco-friendly apartment hotel near Ban...
- **Папка**: CN13
- **Папка существует**: False
- **Всего файлов**: 12
- **Существует**: 0
- **Отсутствует**: 12
- **Примеры отсутствующих**: Layan_Green/TYPE_A_standard_studio_-_work_table_zone_1jpg.jpg, Layan_Green/3D_TYPE_A_-_standard_studio_2_single_1_doublejpg.jpg, Layan_Green/Building_Hjpg.jpg, Layan_Green/Drone_photo_-_1_and_2_phasesjpg.jpg, Layan_Green/Main_pool_and_bridgejpg.jpg

### 17. Forms of property ownership in Thailand. Leashold ...
- **Папка**: Forms_of_property_ownership_in
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: формы_собственности.jpg

### 18. Remote purchase of real estate in Thailand...
- **Папка**: Remote_purchase_of_real_estate
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: Удаленная_покупка_мин.jpg

### 19. 2-story townhouse in Ratsada area...
- **Папка**: 2-story_townhouse_in_Ratsada_a
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: IMG-20231106-WA0112.jpg

### 20. 2-story townhouse in Chalong...
- **Папка**: 2-story_townhouse_in_Chalong
- **Папка существует**: False
- **Всего файлов**: 1
- **Существует**: 0
- **Отсутствует**: 1
- **Примеры отсутствующих**: IMG-20231112-WA0008.jpg

