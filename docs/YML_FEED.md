# Yandex YML feed

The project now exposes the inventory feed that matches the Yandex real-estate spec.

## Endpoint

- URL: `/feeds/yandex-real-estate.xml`
- Method: `GET`
- Optional query parameter `lang` allows building the feed with a specific locale (defaults to `ru`).
- Response type: `application/xml`.
- The response is generated on every request; there is no cached file, so the feed always reflects the current database state.

Example local check:

```bash
python manage.py runserver
curl -s http://127.0.0.1:8000/feeds/yandex-real-estate.xml | head
```

## Data sources

Only active properties with status `available` and at least one price are exported. Each offer contains:

- name, URL, price, currency, single category (`id=1`), vendor, description;
- up to 10 unique pictures (main gallery, intro and floorplan) with the fallback placeholder `/static/images/no-image.svg` if a property lacks media;
- required params `Конверсия` (views + featured priority) and `Тип предложения` (Продажа/Аренда), plus additional metadata when the data exists (address, coordinates, floors, year built, land area, publication date, etc.).

The generator enforces Yandex limits (30k offers, 10 pictures per offer) and skips objects without a usable price or URL.

## Sets

Set metadata is emitted in the `<sets>` block and is linked to offers via `<set-ids>`:

- deal type collections: продажа / аренда (only when there are ≥3 priced listings);
- property type collections: every `PropertyType` with ≥3 listings;
- district collections: every district with ≥3 listings.

The first image of the first offer that belongs to a set becomes a preview image for that set.

## Site metadata

The `<shop>` block now relies on three settings that can be overridden in `.env`:

```env
SITE_NAME="Undersun Estate"
SITE_COMPANY_NAME="Undersun Estate Co., Ltd."
SITE_URL="https://undersunestate.com"
```

These default values live in `config/settings/base.py` and are also used by the feed generator for fallbacks when it needs an absolute URL.

## Notes & limitations

- Optional spec fields such as `Число объявлений`, `Тип парковки`, `Рынок жилья`, etc. are not exported because the project currently has no reliable data for them.
- The feed requires database access; generating it without a configured DB connection will fail.
- The XML is produced on the fly. If Yandex requires a static file, hook the endpoint up to your storage or schedule periodic downloads.
