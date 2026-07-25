import { expect, test, type Page } from '@playwright/test';

const mapResponse = {
  success: true, mode: 'properties', properties: [{ id: 1, slug: 'test-villa', lat: 7.88, lng: 98.39, title: 'Test villa', price: '$100', property_type_label: 'Villa', location: 'Kathu', image_url: '', bedrooms: 3, bathrooms: 2, area: 120, url: '/en/property/test-villa/' }], aggregates: [], total_count: 1, viewport_count: 1, visible_count: 1, aggregate_count: 0, truncated: false, next_action: 'none', server_timing_ms: 12,
};

const cardsResponse = {
  success: true,
  properties: mapResponse.properties,
  page: 1,
  page_size: 30,
  has_next: false,
  next_page: null,
  server_timing_ms: 8,
};

const aggregateResponse = {
  success: true, mode: 'aggregates', properties: [], aggregates: [{ id: 'grid:1', lat: 7.88, lng: 98.39, count: 8 }], total_count: 8, viewport_count: 8, visible_count: 0, aggregate_count: 1, truncated: false, next_action: 'zoom_in', server_timing_ms: 12,
};

const overlappingResponse = {
  ...mapResponse,
  properties: [mapResponse.properties[0], { ...mapResponse.properties[0], id: 2, slug: 'second-villa', title: 'Second villa', price: '$200', url: '/en/property/second-villa/' }],
  total_count: 2,
  viewport_count: 2,
  visible_count: 2,
};

const overlappingMarkerResponse = {
  ...overlappingResponse,
  properties: overlappingResponse.properties.map(({ id, lat, lng }) => ({ id, lat, lng })),
};

const districtOverlayResponse = {
  success: true,
  districts: [],
  geojson: { type: 'FeatureCollection', features: [{ type: 'Feature', properties: { slug: 'kathu' }, geometry: { type: 'Polygon', coordinates: [[[98.25, 7.8], [98.45, 7.8], [98.45, 8], [98.25, 8], [98.25, 7.8]]] } }] },
};

const edgeProperties = [
  { label: 'north-west', lat: 8.18, lng: 98.12 },
  { label: 'north-east', lat: 8.18, lng: 98.68 },
  { label: 'south-west', lat: 7.56, lng: 98.12 },
  { label: 'south-east', lat: 7.56, lng: 98.68 },
];

const longLocalizedTitles = {
  ru: 'Просторная современная вилла с четырьмя спальнями, панорамным бассейном и видом на закат в тихом районе Пхукета',
  en: 'Spacious modern four-bedroom villa with a panoramic pool and sunset views in a quiet Phuket neighbourhood',
  th: 'วิลล่าสมัยใหม่ขนาดกว้างขวางสี่ห้องนอนพร้อมสระว่ายน้ำพาโนรามาและวิวพระอาทิตย์ตกในย่านเงียบสงบของภูเก็ต',
};

function responseForSelectedProperty(property: typeof mapResponse.properties[number]) {
  return {
    ...mapResponse,
    properties: [property],
    selected_property_id: property.id,
    selected_property: property,
  };
}

async function expectPopupWithinMapWithoutScroll(page: Page) {
  const popup = page.locator('.maplibregl-popup');
  const mapCanvas = page.locator('.map-canvas');
  await expect(popup).toBeVisible();
  const [popupBox, mapBox] = await Promise.all([popup.boundingBox(), mapCanvas.boundingBox()]);
  expect(popupBox).not.toBeNull();
  expect(mapBox).not.toBeNull();
  expect(popupBox!.x).toBeGreaterThanOrEqual(mapBox!.x);
  expect(popupBox!.y).toBeGreaterThanOrEqual(mapBox!.y);
  expect(popupBox!.x + popupBox!.width).toBeLessThanOrEqual(mapBox!.x + mapBox!.width);
  expect(popupBox!.y + popupBox!.height).toBeLessThanOrEqual(mapBox!.y + mapBox!.height);
  await expect(popup.locator('.maplibregl-popup-content')).toHaveCSS('overflow-y', 'hidden');
  expect(await popup.locator('.maplibregl-popup-content').evaluate((element) => element.scrollHeight <= element.clientHeight + 1)).toBe(true);
}

async function expectMapCanvasRendered(page: Page) {
  const canvas = page.locator('.map-canvas canvas');
  await expect(canvas).toBeVisible();
  await expect(page.locator('.map-canvas')).toHaveAttribute('data-map-ready', 'true');
  expect(await canvas.evaluate((element) => element instanceof HTMLCanvasElement && element.width > 0 && element.height > 0)).toBe(true);
  // WebGL maps do not guarantee a readable drawing buffer. A browser screenshot
  // validates that the composited map surface exists without relying on readPixels.
  expect((await canvas.screenshot()).byteLength).toBeGreaterThan(8_000);
}

test.beforeEach(async ({ page }) => {
  await page.route('**/en/property/ajax/map/**', (route) => {
    const selectedId = Number(new URL(route.request().url()).searchParams.get('selected'));
    const selectedProperty = mapResponse.properties.find((property) => property.id === selectedId);
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(selectedProperty ? responseForSelectedProperty(selectedProperty) : mapResponse),
    });
  });
  await page.route('**/en/property/ajax/map/cards/**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(cardsResponse) }));
  await page.route('**/en/property/ajax/map-districts/**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(districtOverlayResponse) }));
});

test('district filter highlights the selected district on the map', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'District overlay is verified on desktop');
  await page.goto('/e2e/index.html');
  const mapCanvas = page.locator('.map-canvas');
  await expect(mapCanvas).toHaveAttribute('data-map-ready', 'true');
  await page.getByRole('button', { name: 'Filters' }).click();
  await page.getByRole('combobox', { name: 'District' }).selectOption('kathu');
  await expect(mapCanvas).toHaveAttribute('data-selected-district', 'kathu');
});

test('desktop filters update URL and state survives navigation back', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Desktop sidebar interaction');
  await page.goto('/e2e/index.html');
  await expect(page.locator('.map-canvas')).toBeVisible();
  await page.getByRole('button', { name: 'Filters' }).click();
  await page.getByRole('radio', { name: 'Sale' }).check();
  await expect(page).toHaveURL(/deal_type=sale/);
  await page.goto('/e2e/index.html?deal_type=rent');
  await expect(page.getByRole('radio', { name: 'Rent' })).toBeChecked();
  await page.goBack();
  await expect(page.getByRole('radio', { name: 'Sale' })).toBeChecked();
});

test('desktop bathroom and total-area filters persist in the map request', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Expanded map filters are verified on desktop');
  const requestedUrls: string[] = [];
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => {
    requestedUrls.push(route.request().url());
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(mapResponse) });
  });
  await page.route('**/en/property/ajax/map/cards/**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(cardsResponse) }));

  await page.goto('/e2e/index.html');
  await page.getByRole('button', { name: 'Filters' }).click();
  const bathroomOptions = page.locator('fieldset.map-filter-sidebar__option-group').filter({ hasText: 'Bathrooms' }).locator('label');
  await expect(bathroomOptions).toHaveCount(4);
  const bathroomOptionTops = await bathroomOptions.evaluateAll((elements) => elements.map((element) => element.getBoundingClientRect().top));
  expect(Math.max(...bathroomOptionTops) - Math.min(...bathroomOptionTops)).toBeLessThan(2);
  await expect(page.locator('fieldset.map-filter-sidebar__area')).toContainText('Area, m²');
  await page.locator('fieldset').filter({ hasText: 'Bathrooms' }).getByRole('checkbox', { name: '4+' }).check();
  await expect(page).toHaveURL(/bathrooms=4%2B/);

  await page.getByLabel('Area from').fill('200');
  await expect(page).toHaveURL(/min_area=200/);
  expect(requestedUrls.some((url) => new URL(url).searchParams.getAll('bathrooms').includes('4+'))).toBe(true);
  expect(requestedUrls.some((url) => new URL(url).searchParams.get('min_area') === '200')).toBe(true);
});

test('desktop distinguishes list, map-area, and total result counts', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Result count semantics are verified on desktop');
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...mapResponse, total_count: 12, viewport_count: 8, visible_count: 4, truncated: true, next_action: 'zoom_in' }),
  }));
  await page.goto('/e2e/index.html');

  const summary = page.locator('.map-results-panel__summary');
  await expect(summary).toContainText('1 In list');
  await expect(summary).toContainText('4 On map');
  await expect(summary).toContainText('8 In area');
  await expect(summary).toContainText('12 Total');
  await expect(summary).toContainText('Zoom in to see all properties');
});

test('desktop sort is reflected in the URL and uses the server response order', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Server-backed sorting is verified on desktop');
  const lowPriceProperty = { ...mapResponse.properties[0], id: 11, slug: 'low-price-villa', title: 'Low price villa', price: '$100', url: '/en/property/low-price-villa/' };
  const highPriceProperty = { ...mapResponse.properties[0], id: 12, slug: 'high-price-villa', title: 'High price villa', price: '$900', url: '/en/property/high-price-villa/' };
  const requestedSorts: string[] = [];

  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => {
    const sort = new URL(route.request().url()).searchParams.get('sort') || 'recommended';
    requestedSorts.push(sort);
    const properties = sort === 'price_desc' ? [highPriceProperty, lowPriceProperty] : [lowPriceProperty, highPriceProperty];
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ ...mapResponse, properties, total_count: 2, viewport_count: 2, visible_count: 2, sort }),
    });
  });

  await page.goto('/e2e/index.html');
  await expect(page.locator('.map-results-panel__card').first()).toContainText('Low price villa');
  await page.getByLabel('Sort').selectOption('price_desc');

  await expect(page).toHaveURL(/sort=price_desc/);
  await expect(page.locator('.map-results-panel__card').first()).toContainText('High price villa');
  expect(requestedSorts).toContain('price_desc');
});

test('desktop list loads the next card page only after scrolling', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Infinite card list is verified on desktop');
  const properties = Array.from({ length: 35 }, (_, index) => ({
    ...mapResponse.properties[0],
    id: index + 1,
    slug: `card-${index + 1}`,
    title: `Card ${index + 1}`,
    url: `/en/property/card-${index + 1}/`,
  }));
  const requestedPages: string[] = [];
  await page.unroute('**/en/property/ajax/map/cards/**');
  await page.route('**/en/property/ajax/map/cards/**', (route) => {
    const pageNumber = new URL(route.request().url()).searchParams.get('page') || '1';
    requestedPages.push(pageNumber);
    const start = (Number(pageNumber) - 1) * 30;
    const pageProperties = properties.slice(start, start + 30);
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ success: true, properties: pageProperties, page: Number(pageNumber), page_size: 30, has_next: start + 30 < properties.length, next_page: start + 30 < properties.length ? Number(pageNumber) + 1 : null, server_timing_ms: 8 }),
    });
  });

  await page.goto('/e2e/index.html');
  const panel = page.locator('.map-results-panel');
  await expect(panel.locator('.map-results-panel__card')).toHaveCount(30);
  expect(requestedPages).toEqual(['1']);
  await panel.evaluate((element) => { element.scrollTop = element.scrollHeight; element.dispatchEvent(new Event('scroll')); });
  await expect(panel.locator('.map-results-panel__card')).toHaveCount(35);
  expect(requestedPages).toEqual(['1', '2']);
});

test('desktop keeps the current results visible while a filtered request is pending', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Pending map results are verified on desktop');
  let releaseSaleResponse: (() => void) | undefined;
  let markSaleRequest: (() => void) | undefined;
  const saleRequestStarted = new Promise<void>((resolve) => { markSaleRequest = resolve; });
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', async (route) => {
    const selected = new URL(route.request().url()).searchParams.has('selected');
    if (new URL(route.request().url()).searchParams.get('deal_type') === 'sale') {
      markSaleRequest?.();
      await new Promise<void>((resolve) => { releaseSaleResponse = resolve; });
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(selected ? responseForSelectedProperty({ ...mapResponse.properties[0], price: '$200' }) : { ...mapResponse, properties: [{ ...mapResponse.properties[0], price: '$200' }] }),
      });
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(selected ? responseForSelectedProperty(mapResponse.properties[0]) : mapResponse) });
  });
  await page.route('**/en/property/ajax/map/cards/**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(cardsResponse) }));
  await page.goto('/e2e/index.html?selected=1');
  await expect(page.locator('.maplibregl-popup')).toContainText('$100');
  await page.getByRole('button', { name: 'Filters' }).click();
  await page.getByRole('radio', { name: 'Sale' }).check();
  await saleRequestStarted;

  await expect(page.locator('.maplibregl-popup')).toContainText('$100');
  await expect(page.locator('.map-results-panel')).toContainText('Test villa');

  releaseSaleResponse?.();
  await expect(page.locator('.maplibregl-popup')).toContainText('$200');
});

test('desktop keeps the current results visible after a filtered request fails', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Failed map requests are verified on desktop');
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => {
    const selected = new URL(route.request().url()).searchParams.has('selected');
    if (new URL(route.request().url()).searchParams.get('deal_type') === 'sale') {
      return route.fulfill({ status: 400, contentType: 'application/json', body: JSON.stringify({ success: false }) });
    }
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(selected ? responseForSelectedProperty(mapResponse.properties[0]) : mapResponse) });
  });
  await page.route('**/en/property/ajax/map/cards/**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(cardsResponse) }));
  await page.goto('/e2e/index.html?selected=1');
  await expect(page.locator('.maplibregl-popup')).toContainText('$100');
  await page.getByRole('button', { name: 'Filters' }).click();
  await page.getByRole('radio', { name: 'Sale' }).check();

  await expect(page.getByRole('alert')).toContainText('Unavailable');
  await expect(page.locator('.maplibregl-popup')).toContainText('$100');
  await expect(page.locator('.map-results-panel')).toContainText('Test villa');
});

test('currency change refetches prices without clearing the selected object', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Currency refresh is verified on desktop');
  let useThb = false;
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => {
    const selected = new URL(route.request().url()).searchParams.has('selected');
    const payload = useThb ? {
      ...mapResponse,
      properties: [{ ...mapResponse.properties[0], price: '฿3,600,000' }],
    } : mapResponse;
    const property = payload.properties[0];
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(selected ? responseForSelectedProperty(property) : payload) });
  });
  await page.route('**/en/property/ajax/map/cards/**', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(cardsResponse) }));
  await page.goto('/e2e/index.html?selected=1');
  await expect(page.locator('.maplibregl-popup')).toContainText('$100');

  useThb = true;
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('currencyChanged', { detail: { currency: 'THB', symbol: '฿' } })));

  await expect(page.locator('main')).toHaveAttribute('data-map-currency', 'THB');
  await expect(page.locator('.maplibregl-popup')).toContainText('฿3,600,000');
  await expect(page).toHaveURL(/selected=1/);
});

test('desktop filter drawer preserves filters when closed', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Desktop filter drawer interaction');
  await page.goto('/e2e/index.html');
  await expect(page.locator('.map-results-panel')).toBeVisible();
  await page.getByRole('button', { name: 'Filters' }).click();
  await expect(page.getByRole('complementary', { name: 'Filters' })).toBeVisible();
  await page.getByRole('radio', { name: 'Sale' }).check();
  await page.getByRole('button', { name: 'Filters' }).click();
  await expect(page.locator('.map-filter-sidebar')).toHaveCount(0);
  await page.getByRole('button', { name: 'Filters' }).click();
  await expect(page.getByRole('radio', { name: 'Sale' })).toBeChecked();
});

test('tablet and mobile open filters in an accessible dialog', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name === 'desktop', 'Bottom sheet interaction');
  await page.goto('/e2e/index.html');
  await page.getByRole('button', { name: 'Filters' }).click();
  const dialog = page.getByRole('dialog', { name: 'Filters' });
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveCSS('background-color', 'rgb(255, 255, 255)');
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('desktop list card selects a property and opens a map popup', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Desktop property list interaction');
  await page.goto('/e2e/index.html?selected=1');
  const popup = page.locator('.maplibregl-popup');
  await expect(popup).toBeVisible();
  await expect(popup.locator('.maplibregl-popup-content')).toHaveCSS('overflow-y', 'hidden');
  const box = await popup.boundingBox();
  const mapBox = await page.locator('.map-canvas').boundingBox();
  expect(box).not.toBeNull();
  expect(mapBox).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(mapBox!.x);
  expect(box!.y).toBeGreaterThanOrEqual(mapBox!.y);
  expect(box!.x + box!.width).toBeLessThanOrEqual(mapBox!.x + mapBox!.width);
  expect(box!.y + box!.height).toBeLessThanOrEqual(mapBox!.y + mapBox!.height);
  await expect(page.locator('.map-results-panel__card.is-selected')).toBeVisible();
  await expect(page.locator('.map-canvas canvas')).toBeVisible();
});

test('desktop card hover and focus highlight its marker without opening a popup', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Desktop card-marker linkage');
  await page.goto('/e2e/index.html');
  const card = page.locator('.map-results-panel__card').first();
  const mapCanvas = page.locator('.map-canvas');

  await card.hover();
  await expect(card).toHaveClass(/is-highlighted/);
  await expect(mapCanvas).toHaveAttribute('data-highlighted-property', '1');
  await expect(page.locator('.maplibregl-popup')).toHaveCount(0);
  await page.locator('.map-results-panel__summary').hover();
  await expect(card).not.toHaveClass(/is-highlighted/);

  await card.focus();
  await expect(mapCanvas).toHaveAttribute('data-highlighted-property', '1');
  await page.keyboard.press('Tab');
  await expect(card).not.toHaveClass(/is-highlighted/);
  await expect(mapCanvas).not.toHaveAttribute('data-highlighted-property', '1');
});

test('desktop popup stays within the map at all four map edges', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Edge positioning is verified on desktop');
  let property = mapResponse.properties[0];
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify(responseForSelectedProperty(property)),
  }));

  for (const [index, edge] of edgeProperties.entries()) {
    property = {
      ...mapResponse.properties[0],
      id: index + 11,
      slug: `edge-${edge.label}`,
      title: `Popup at ${edge.label}`,
      lat: edge.lat,
      lng: edge.lng,
      url: `/en/property/edge-${edge.label}/`,
    };
    await page.goto(`/e2e/index.html?selected=${property.id}`);
    await expectPopupWithinMapWithoutScroll(page);
    await expectMapCanvasRendered(page);
    await expect(page.locator('.maplibregl-popup-content')).toHaveScreenshot(`popup-edge-${edge.label}.png`, { animations: 'disabled' });
  }
});

test('desktop popup supports long Russian, English and Thai content without clipping', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Localized popup regression is verified on desktop');
  let property = mapResponse.properties[0];
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify(responseForSelectedProperty(property)),
  }));

  for (const [language, title] of Object.entries(longLocalizedTitles)) {
    property = { ...mapResponse.properties[0], id: 31, title, url: `/en/property/long-${language}/` };
    await page.goto('/e2e/index.html?selected=31');
    await expectPopupWithinMapWithoutScroll(page);
    await expect(page.locator('.maplibregl-popup-content')).toHaveScreenshot(`popup-long-${language}.png`, { animations: 'disabled' });
  }
});

test('narrow desktop renders an empty-image popup and a nonblank canvas', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Narrow desktop is verified in the desktop browser');
  await page.setViewportSize({ width: 1024, height: 720 });
  const property = {
    ...mapResponse.properties[0],
    id: 41,
    title: longLocalizedTitles.en,
    image_url: '',
    url: '/en/property/empty-image/',
  };
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify(responseForSelectedProperty(property)),
  }));
  await page.goto('/e2e/index.html?selected=41');

  await expectPopupWithinMapWithoutScroll(page);
  await expectMapCanvasRendered(page);
  await expect(page.locator('.maplibregl-popup img')).toHaveCount(0);
  await expect(page.locator('.maplibregl-popup-content')).toHaveScreenshot('popup-narrow-empty-image.png', { animations: 'disabled' });
});

test('desktop popup remains mounted while the viewport state changes', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Popup stability is verified on desktop');
  await page.goto('/e2e/index.html?selected=1');
  const popup = page.locator('.maplibregl-popup');
  await expect(popup).toBeVisible();
  await popup.evaluate((element) => { (window as Window & { mapPopupElement?: Element }).mapPopupElement = element; });

  const canvas = page.locator('.map-canvas canvas');
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await page.mouse.down();
  await page.mouse.move(box!.x + box!.width / 2 + 80, box!.y + box!.height / 2 + 40, { steps: 5 });
  await page.mouse.up();
  await page.waitForTimeout(400);

  await expect(popup).toBeVisible();
  expect(await page.evaluate(() => (window as Window & { mapPopupElement?: Element }).mapPopupElement === document.querySelector('.maplibregl-popup'))).toBe(true);
});

test('desktop result card selects the matching map property', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Desktop property list interaction');
  await page.goto('/e2e/index.html');
  await page.locator('.map-results-panel__card').click();
  await expect(page.locator('.maplibregl-popup')).toBeVisible();
  await expect(page).toHaveURL(/selected=1/);
  await expect(page.locator('.map-results-panel__card.is-selected')).toBeVisible();
});

test('property pin opens the selected property map popup', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Map pin interaction is verified on the desktop popup');
  await page.goto('/e2e/index.html');
  const canvas = page.locator('.map-canvas canvas');
  await expect(canvas).toBeVisible();
  await expect(page.locator('.map-canvas')).toHaveAttribute('data-map-ready', 'true');
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await expect(canvas).toHaveCSS('cursor', 'pointer');
  await page.mouse.click(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await expect(page.locator('.maplibregl-popup')).toBeVisible();
  await expect(page).toHaveURL(/selected=1/);
});

test('aggregate click loads detailed pins for the selected area', async ({ page }, testInfo) => {
  test.skip(!['desktop', 'mobile'].includes(testInfo.project.name), 'Aggregate drill-down is verified on desktop and mobile');
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => {
    const zoom = Number(new URL(route.request().url()).searchParams.get('zoom'));
    const payload = zoom > 10 ? mapResponse : aggregateResponse;
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(payload) });
  });
  await page.goto('/e2e/index.html');
  const canvas = page.locator('.map-canvas canvas');
  await expect(page.locator('.map-canvas')).toHaveAttribute('data-map-ready', 'true');
  await expect(page.locator('main[data-map-response-mode="aggregates"]')).toBeVisible();
  await page.waitForTimeout(300);
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.move(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await expect(canvas).toHaveCSS('cursor', 'pointer');
  await page.mouse.click(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await expect(page.locator('main[data-map-response-mode="properties"]')).toBeVisible();
});

test('overlapping property pins offer every property at the location', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Overlapping pin selection is verified on desktop');
  await page.unroute('**/en/property/ajax/map/**');
  await page.unroute('**/en/property/ajax/map/cards/**');
  await page.route('**/en/property/ajax/map/**', (route) => {
    const selectedId = Number(new URL(route.request().url()).searchParams.get('selected'));
    const selectedProperty = overlappingResponse.properties.find((property) => property.id === selectedId);
    return route.fulfill({ contentType: 'application/json', body: JSON.stringify(selectedProperty ? responseForSelectedProperty(selectedProperty) : overlappingMarkerResponse) });
  });
  await page.route('**/en/property/ajax/map/cards/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ ...cardsResponse, properties: overlappingResponse.properties }),
  }));
  await page.goto('/e2e/index.html');
  const canvas = page.locator('.map-canvas canvas');
  await expect(page.locator('.map-canvas')).toHaveAttribute('data-map-ready', 'true');
  const box = await canvas.boundingBox();
  expect(box).not.toBeNull();
  await page.mouse.click(box!.x + box!.width / 2, box!.y + box!.height / 2);
  await expect(page.locator('.map-property-selection')).toBeVisible();
  await page.locator('.map-property-selection').getByRole('button', { name: /Second villa/ }).click();
  await expect(page.locator('.maplibregl-popup')).toContainText('Second villa');
});

test('mobile result sheet is visible without clipping', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'Mobile result sheet interaction');
  await page.goto('/e2e/index.html?selected=1');
  const sheet = page.locator('.map-mobile-property-sheet');
  await expect(sheet).toBeVisible();
  const box = await sheet.boundingBox();
  const viewportHeight = await page.evaluate(() => window.innerHeight);
  expect(box).not.toBeNull();
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewportHeight);
  await page.getByRole('button', { name: 'Close' }).click();
  await expect(sheet).toHaveCount(0);
  await expect(page).not.toHaveURL(/selected=/);
});

test('mobile map and list views reuse results while preserving selection and list scroll', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile', 'Mobile map/list switch is verified on mobile');
  const properties = Array.from({ length: 40 }, (_, index) => ({
    ...mapResponse.properties[0],
    id: index + 1,
    slug: `mobile-${index + 1}`,
    title: `Mobile property ${index + 1}`,
    url: `/en/property/mobile-${index + 1}/`,
  }));
  let requestCount = 0;
  await page.unroute('**/en/property/ajax/map/**');
  await page.route('**/en/property/ajax/map/**', (route) => {
    requestCount += 1;
    const selected = new URL(route.request().url()).searchParams.has('selected');
    const payload = { ...mapResponse, properties, total_count: 40, viewport_count: 40, visible_count: 40 };
    return route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify(selected ? responseForSelectedProperty(properties[0]) : payload),
    });
  });
  await page.route('**/en/property/ajax/map/cards/**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({ success: true, properties: properties.slice(0, 30), page: 1, page_size: 30, has_next: true, next_page: 2, server_timing_ms: 8 }),
  }));
  await page.goto('/e2e/index.html?selected=1');
  await expect(page.locator('.map-mobile-property-sheet')).toBeVisible();

  await page.getByRole('tab', { name: 'List' }).click();
  const panel = page.locator('.map-results-panel');
  await expect(panel).toBeVisible();
  await expect(panel.locator('.map-results-panel__card.is-selected')).toBeVisible();
  await panel.evaluate((element) => { element.scrollTop = 520; });
  const scrollBeforeSwitch = await panel.evaluate((element) => element.scrollTop);

  await page.getByRole('tab', { name: 'Map' }).click();
  await expect(page.locator('.map-mobile-property-sheet')).toBeVisible();
  await page.getByRole('tab', { name: 'List' }).click();

  expect(await panel.evaluate((element) => element.scrollTop)).toBe(scrollBeforeSwitch);
  expect(requestCount).toBe(1);
  await expect(page.locator('main')).toHaveAttribute('data-map-selected-property', '1');
});

test('reduced-motion mode disables map shell animation', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/e2e/index.html');
  await expect(page.locator('.map-app-layout')).toHaveCSS('--map-motion-enabled', '0');
});
