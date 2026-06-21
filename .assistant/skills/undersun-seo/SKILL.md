---
name: undersun-seo
description: Use when implementing, auditing, or reviewing SEO for the Undersun Estate multilingual Django site. Focuses on indexability, hreflang/canonical, server-rendered metadata, schema, image SEO, property/catalog/blog SEO, programmatic landing safeguards, Google generative AI search guidance, and non-Google LLM/GEO visibility.
---

# Undersun SEO Skill

Use this skill together with:

- `$undersun-frontend` when SEO changes touch Django templates, Tailwind/CSS, static JS, page UX, or frontend rendering;
- project `AGENTS.md` for current app map, routing, build pipeline, and Undersun-specific implementation notes.

Use it when the task involves:

- homepage, catalog, location, property detail, service, or blog SEO;
- metadata, canonical, robots, sitemap, redirects, or `hreflang`;
- schema / JSON-LD work;
- image SEO, video SEO, gallery SEO, or CLS-sensitive media;
- `SEOPage`, `SEOTemplate`, `SEOContentBlock`, or property SEO overrides;
- programmatic SEO landings for property types, deal types, districts, locations, or investment topics;
- SEO review before release.

Do NOT use this skill for:

- paid ads, backlink outreach, or reputation campaigns;
- generic copywriting not intended for indexable public pages;
- GitHub repository SEO;
- non-Undersun projects.

## Project SEO Position

This product is:

- a multilingual real estate agency website for Phuket;
- a public catalog of sale/rent properties with lead-generation forms;
- a local expertise and content-marketing site in `ru`, `en`, and `th`;
- a Django server-rendered site with page-specific vanilla JS.

This product is NOT:

- a property marketplace with user-generated listings;
- a financial, legal, or immigration advisory service;
- a guarantee of rental yield, resale value, visa outcome, or purchase approval.

All SEO work must preserve those boundaries.

## Audit Workflow

Use an evidence-first workflow:

1. Check page type:
   - homepage;
   - catalog/list page;
   - property detail page;
   - district/location page;
   - service/static page;
   - blog list/detail page;
   - programmatic SEO landing;
   - private/admin/AJAX endpoint.
2. Collect evidence:
   - raw initial HTML and rendered HTML when JavaScript or lazy UI may affect SEO;
   - `title`;
   - `description`;
   - H1;
   - canonical;
   - robots;
   - `hreflang`;
   - schema / JSON-LD;
   - headings;
   - internal links;
   - image and video usage;
   - visible property facts, prices, currencies, locations, agent/contact details, dates, and language variants where relevant.
3. Evaluate findings with:
   - `Finding`;
   - `Evidence`;
   - `Impact`;
   - `Fix`.
4. Mark confidence as:
   - `Confirmed`;
   - `Likely`;
   - `Hypothesis`.
5. Prioritize by:
   - indexability, robots, canonical, redirect, and `hreflang` risk first;
   - then metadata/schema correctness;
   - then content quality, real estate trust, and duplicate/thin-page risks;
   - then image/video SEO, CLS, and mobile rendering;
   - then nice-to-have improvements.

Do not give vague SEO advice without pointing to concrete page evidence.

For repeat audits, record durable baselines in the active project plan or audit document with the tool name, URL, device, date, and source of data. Do not rely on memory or create hidden cache files unless the user explicitly wants an artifact workflow.

## Required Checks For Public Pages

Every indexable public page should be checked for:

- unique server-rendered `title`;
- meaningful server-rendered `description`;
- one clear H1;
- sensible canonical URL;
- correct language-prefixed URL behavior for `ru`, `en`, and `th`;
- correct `hreflang` alternates, including `x-default` only when the implementation actually supports it;
- Open Graph metadata;
- human-readable slug;
- crawlable server-rendered primary content;
- internal links to adjacent relevant pages;
- stable mobile-first rendering;
- no accidental `noindex`, blocked robots behavior, or canonical to the wrong locale/page.

When applicable, also require:

- JSON-LD matching visible content;
- breadcrumbs;
- `published_at` / `updated_at` for blog content;
- author or team attribution where content relies on expertise;
- property facts: deal type, property type, price, currency, location, district, bedrooms, bathrooms, area, status, and contact/agent where available;
- clear dates or freshness signals for market, legal, tax, visa, or investment content.

## Multilingual SEO Rules

Undersun uses `ru`, `en`, and `th`; localized public routes live under language prefixes.

Verify:

- each indexable localized page has a self-canonical in the same language;
- translated versions point to each other with `hreflang`;
- titles, descriptions, H1s, slugs, and body content are localized, not mixed-language shells;
- missing translations do not create empty or misleading indexable pages;
- currency display is localized for UX but does not create separate indexable currency URLs unless explicitly designed;
- language switchers preserve the equivalent page when possible and avoid linking users to unrelated fallbacks without intent.

Do not remove `hreflang` or language prefixes to simplify implementation.

For each `hreflang` set, verify:

- every localized URL has a self-reference that exactly matches its canonical URL, including protocol, host, path, and trailing slash;
- every alternate relationship is bidirectional across `ru`, `en`, and `th`;
- `x-default` is present only when the implementation intentionally supports a fallback page;
- non-canonical, filtered, paginated, map-state, or redirected URLs are not included in the alternate set.

For multilingual quality, check section-level parity and locale fit:

- equivalent pages keep the same core property facts, service claims, dates, prices, availability, and schema facts;
- localized pages do not leak Russian, English, or Thai UI microcopy into `aria-label`, placeholders, form labels, image alt text, schema, JSON bootstrap data, or hidden modal text;
- dates, currencies, phone/contact formatting, legal references, and CTAs fit the target locale without changing the business facts.

## Private And Non-Indexable Boundaries

These areas should stay non-indexable or outside public SEO scope:

- `/admin/`;
- `/rosetta/`;
- `/i18n/`;
- `/currency/` session switcher routes;
- `/tinymce/`;
- `/admin-ajax/`;
- `/jsi18n/`;
- JSON/AJAX lead endpoints;
- internal import, parsing, and operational tooling;
- form submission success/error payloads;
- private or staff-only views.

Verify:

- no sensitive lead, user, staff, or operational data appears in public HTML, metadata, schema, or analytics markup;
- private or utility endpoints are not exposed as SEO landing pages;
- no private page canonicals point to unrelated public pages.

## Content And Trust Rules

SEO copy must support trust, local expertise, and accurate property decisions.

Prefer:

- specific Phuket district and neighborhood context;
- real property facts and tradeoffs;
- developer/project specifics where known;
- original agency observations;
- buyer/renter intent framing;
- clear distinctions between sale, rent, villa, condo, land, commercial, investment, and relocation content;
- practical next steps through existing lead/contact patterns.

Avoid:

- generic keyword filler;
- cloned descriptions with only location or property type swapped;
- fake urgency or unsupported scarcity claims;
- guaranteed ROI, yield, resale, legal, tax, visa, or construction promises;
- claims not supported by visible property data or editorial evidence;
- content created only to target every possible long-tail variation.

For market, legal, investment, visa, tax, or financing-adjacent pages, keep wording informational and attribute uncertainty. Do not turn real estate SEO pages into professional legal, tax, or financial advice.

Treat LLM misinterpretation risk as a content quality issue. Be especially careful with foreign ownership, freehold quota, leasehold renewals, Thai company ownership, Blue Book / Tabien Baan, land titles, Land Department registration, taxes and transfer fees, rental guarantees, ROI/yield/resale/liquidity, visa/residency/relocation claims, construction dates, developer reliability, and off-plan risks.

For these topics, prefer safer wording such as "usually", "may", "depends on the project", "must be checked before purchase", "requires legal review", "as of the article update date", and "not legal, tax, financial, or immigration advice".

## E-E-A-T Evidence For Real Estate

Treat E-E-A-T as an evaluation framework, not a tag, schema property, score, or single ranking switch. The practical goal is to make experience, expertise, authoritativeness, and trust visible in the page and site evidence.

For Undersun, prove E-E-A-T through the content and interface:

- Experience: original property, district, project, view, infrastructure, and team photos; captions that explain what is shown; agent notes about real tradeoffs; freshness signals such as updated price, status, and availability.
- Expertise: named agents or authors; team pages with languages, role, and specialization; reviewed-by attribution for investment, purchase-process, legal, tax, visa, or financing-adjacent pages; explanations grounded in actual Phuket and Thai real estate practice.
- Authoritativeness: clear company/about page; consistent brand, phone, email, address/service area, messengers, and social profiles; links between property, district, service, and blog expertise; external references or official sources where rules and market facts are discussed.
- Trust: transparent contact paths; privacy/cookie/form-processing policies; no fake ratings, reviews, scarcity, or guarantees; visible facts that match backend data, metadata, schema, and translated page variants.

For property pages, local pages, and editorial guides, prefer evidence that a generic SEO writer could not know: current inventory patterns, neighborhood pros/cons, developer specifics, practical buyer/renter caveats, original media, and agency observations.

Do not claim E-E-A-T in copy. Demonstrate it through verifiable authorship, accurate facts, useful original content, visible business identity, and careful wording around money/legal/life-impacting decisions.

## Google Generative AI Search

Source baseline: Google Search Central, "Optimizing your website for generative AI features on Google Search", last updated 2026-05-15 UTC. Re-check the official page before major SEO policy changes.

Treat AI Overviews and AI Mode as part of normal Google SEO, not as a separate AEO/GEO workflow. Google's generative search features are grounded in the normal Search index, ranking, and quality systems.

Assume two important behaviors:

- Retrieval-augmented generation uses indexed, crawlable, relevant pages as grounding sources. If a page is not indexable, snippet-eligible, technically clear, and useful, AI Search work cannot compensate.
- Query fan-out can explore related sub-questions around the original query. Use this as an editorial research tool to make one strong page answer adjacent user needs, not as a reason to generate many thin pages.

Prioritize:

- indexable, snippet-eligible pages;
- crawlable server-rendered primary content;
- canonical and `hreflang` correctness;
- unique, expert-led, non-commodity content;
- clear paragraph/section/headline structure for humans;
- high-quality relevant images and video;
- clear technical structure and page experience;
- reduced duplicate content and controlled faceted URLs;
- Search Console, Rich Results Test, and rendered HTML validation where practical.

For Undersun Estate, AI-search-ready content should include real local expertise: Phuket district context, developer/project specifics, transaction and legal nuance, agent observations, original media, and current property facts.

When using AI tools to draft SEO copy, keep the output within Google Search Essentials and spam policy expectations: human-edit it, verify facts against backend data, remove generic filler, and add Undersun-specific evidence.

Do not:

- create `llms.txt`, AI text files, Markdown mirrors, or special AI markup as Google Search visibility or ranking shortcuts;
- split pages into artificial "chunks" for AI consumption;
- rewrite content in a special "AI style";
- chase every long-tail wording variation with a new page;
- seek fake mentions or synthetic third-party signals;
- overfocus on schema as an AI Search shortcut;
- create pages primarily to manipulate rankings or AI responses.

Structured data remains useful for rich results, but it is not a special requirement for generative AI search.

For AI-search citation readiness, improve normal page evidence instead of adding artificial AI-only surfaces:

- use answer-first paragraphs under clear H2/H3 headings for important questions;
- make key facts self-contained enough to quote without losing context, especially on market, legal, investment, service, and district pages;
- prefer specific data, source attribution, author/reviewer names, publication/update dates, and original Undersun observations;
- use tables and lists for comparisons, transaction steps, cost components, district tradeoffs, and eligibility constraints;
- keep infographic/SVG data accessible in real DOM text or inline SVG text, not only raster images or background graphics;
- verify buttons, links, selects, forms, modals, maps, and cookie UI have accessible names so browser agents can navigate the page.

Do not recommend `llms.txt`, AI-only Markdown mirrors, artificial content chunks, special "AI citation blocks", or crawler-policy changes as Google AI Search shortcuts. Google Search guidance says AI Overviews and AI Mode do not require new machine-readable files or special markup.

`llms.txt` may still be useful as an optional agentic-browsing or non-Google LLM artifact: a concise source map that helps AI agents understand the site's purpose and key URLs. Treat it as optional, keep it synchronized with visible HTML/schema, and do not present it as a ranking factor or guaranteed AI-citation mechanism.

Discuss AI crawler allow/block policy only when the user asks about non-Google AI visibility, licensing, data-use preferences, or `robots.txt`; distinguish search/browsing bots from training crawlers.

## Non-Google LLM Visibility / GEO Audit

Use this section when the user asks about GEO, LLM visibility, AI search visibility, ChatGPT Search, Perplexity, AI platform, Bing Copilot, browser agents, or how AI systems see the site. Do not confuse this with Google AI Search guidance.

Treat LLM visibility as the ability of non-Google AI systems and browser agents to:

- fetch the public page when allowed;
- identify the page entity and Undersun Estate business entity;
- extract accurate facts from normal visible HTML;
- quote or summarize the page without losing context;
- distinguish Undersun Estate's real estate services from legal, tax, financial, immigration, or investment advice;
- recommend the right Undersun page for the right user intent.

For important public pages, verify entity extraction from visible HTML:

- business name, type, service area, languages, services, contact paths, and trust signals;
- page-specific facts such as property type, deal type, location, price, currency, area, bedrooms, bathrooms, status, update date, author, reviewer, and sources.

For answer suitability, identify the AI-answer intents each page can support. Check whether the page answers the intent near the top, whether the answer is quotable with enough context, whether caveats are present for risky topics, and whether the page links to a better internal source when it is not the best answer.

For citation readiness, prefer concise answer-first paragraphs under clear H2/H3 headings, self-contained factual statements, visible publication/update dates, named author or reviewer where expertise matters, source links for legal/tax/visa/financing/official market facts, original Undersun observations, tables or lists for comparisons and risks, and no unsupported guarantees.

For site-level GEO audits, produce an LLM source map:

| User question | Best Undersun source page | Current readiness | Missing evidence | Recommended fix |
|---|---|---|---|---|

Include core questions around foreign ownership, freehold vs leasehold, best Phuket areas, villas, condos, rentals, off-plan risks, investment risks, taxes and transfer fees, and how to choose a Phuket real estate agent.

Discuss AI crawler policy only when the task explicitly involves non-Google AI visibility, licensing, data-use preferences, or `robots.txt`. Distinguish search/browsing bots, training crawlers, and normal search crawlers such as Googlebot and Bingbot. Do not recommend opening all bots by default; explain the tradeoff between visibility, training restrictions, commercial AI restrictions, and default robots behavior.

When `llms.txt` is explicitly requested or needed to address a Lighthouse Agentic Browsing / discoverability audit, keep it short and factual:

- summarize Undersun Estate's business identity, languages, service area, and service boundaries;
- link only to canonical, maintained public pages;
- include legal/tax/financial/immigration caveats where relevant;
- avoid duplicating volatile property inventory, prices, availability, or claims that can drift from the database;
- verify it does not contradict visible HTML, schema, sitemap, robots policy, or localized page facts.

When the user asks for GEO or LLM visibility, add these sections to the normal SEO review:

1. LLM summary of the page/site
2. Extracted entities and facts
3. Best AI-answer intents
4. Citation-ready sections
5. Missing evidence
6. Misinterpretation risks
7. Recommended answer-first blocks
8. Internal source map
9. Schema and visible-content alignment
10. Priority fixes

## Local Business And Agent-Friendly Readiness

Google's AI search guidance calls out local business, product/service details, and emerging browser-agent use cases. For Undersun, treat this as a practical quality layer, not a speculative protocol project.

Verify:

- public business identity, contacts, logo, social links, address/service area, and opening/contact expectations are consistent across site metadata, schema, footer, contact pages, and Google Business Profile assumptions;
- property/service pages expose the key facts in normal HTML, not only images, hover states, modals, maps, or JavaScript-only widgets;
- forms and CTAs have understandable labels, accessible names, and stable DOM structure;
- browser agents can inspect meaningful DOM, accessibility tree, and rendered page state without needing private sessions or brittle UI steps;
- important comparison facts such as price, bedrooms, area, district, deal type, amenities, and agent contact are machine-readable enough through visible text and truthful schema where appropriate.

Do not add experimental commerce or agent protocols unless the user explicitly asks and the business flow is ready to support them.

## Programmatic SEO Safeguards

This matters especially for:

- sale/rent catalog landings;
- property type pages;
- district and location pages;
- SEO-generated combinations of deal type, property type, bedrooms, budget, district, and lifestyle intent;
- investment, relocation, and lifestyle clusters;
- blog/category/tag archives.

Verify:

- each page has a distinct primary intent;
- pages are not templated clones with only one token swapped;
- title/H1/description differ meaningfully;
- visible on-page content exists beyond metadata and card lists;
- page copy reflects the actual inventory, district, or topic;
- internal links connect to relevant catalog filters, locations, properties, services, and blog content;
- canonical URLs are unique and sensible;
- faceted/filter URLs do not create uncontrolled duplicate indexable surfaces;
- pagination and map/grid variants do not split indexation unintentionally;
- no thin doorway pages.

If a programmatic page has weak unique value, flag it before implementation.

Use these numeric gates for generated SEO landings, not for normal property detail inventory:

- warn before publishing 100+ generated SEO pages without a sampling review;
- require explicit justification before publishing 500+ generated SEO pages;
- flag pages where less than 40% of the main body is genuinely unique to the page;
- treat less than 30% unique main-body content as a hard stop until the template/data strategy changes;
- review at least 5-10% of generated pages manually before release;
- roll out large sets in batches of 50-100 pages, then monitor indexing, impressions, and quality signals for 2-4 weeks before expanding;
- consolidate, noindex, or exclude pages whose source data cannot support standalone user value.

The standalone value test is mandatory: would this page still deserve to exist if no similar generated page existed on the site?

## Schema And Metadata Rules

Use schema only when it matches the page truthfully and is supported by visible content.

Do:

- prefer simple, valid JSON-LD;
- use `Organization`, `LocalBusiness` or real-estate-relevant business schema only when the business details are accurate;
- use `BreadcrumbList` where the hierarchy is clear;
- use article-related schema for blog posts;
- keep property, offer, price, currency, availability, address/location, and image data consistent with the visible page;
- keep metadata, Open Graph, and schema aligned with the localized page language.

Do NOT:

- add fake review or rating schema;
- invent aggregate ratings, prices, amenities, developer names, or availability;
- over-scope schema just to qualify for rich results;
- stuff schema with placeholders or unsupported claims;
- use structured data as a substitute for visible content.

## Property Detail SEO

For property detail pages, verify:

- title and H1 identify the property clearly without keyword stuffing;
- canonical points to the current language detail URL;
- localized URLs and `hreflang` are correct;
- price and currency are visible and consistent with `Property.get_price_in_currency` behavior;
- key facts are server-rendered, not only injected by JavaScript;
- main image and gallery have useful alt text and stable dimensions;
- breadcrumbs reflect catalog hierarchy;
- contact CTA and assigned agent/team data are present where available;
- unavailable, sold, rented, draft, or duplicate properties do not remain indexable unintentionally;
- schema does not promise availability, ratings, or exact address details that are not shown.

## Catalog, Location, And Map SEO

For catalog and location pages, verify:

- indexable landing pages have stable canonical URLs;
- transient filters, sort orders, AJAX map payloads, and session/currency changes do not create duplicate SEO pages;
- server-rendered listings or meaningful landing content are present before JS enhancements;
- district/location pages contain unique local context, not just repeated property grids;
- pagination, load-more behavior, and map/grid state are crawlable or intentionally non-indexable;
- internal links guide users to relevant districts, property types, services, and high-value properties.

When a page is technically healthy but underperforms, check search intent and page-type fit before rewriting:

- transactional queries should usually land on catalog, property-type, district, or property pages, not generic blog posts;
- informational queries should usually land on guides, service pages, FAQs, or editorial content with clear next steps;
- local queries should expose district/location context, inventory, service area, contact paths, and local proof;
- do not force a page type that the current SERP clearly does not reward unless the user is intentionally testing a different strategy.

## Blog And Editorial SEO

For blog pages, verify:

- article metadata is localized and server-rendered;
- visible dates match schema dates;
- author/source attribution exists when the topic relies on expertise;
- content is specific to Phuket, Thai real estate, relocation, investment, or agency experience where relevant;
- image alt text and captions support comprehension;
- AMP pages, if present, are canonicalized correctly and remain consistent with the main article.

## Image, Video, And CLS Checks

For public SEO pages, verify:

- meaningful `alt` text for informative property, district, team, and editorial images;
- decorative images use empty alt when appropriate;
- main property image and hero media have stable dimensions or aspect ratios;
- gallery/lazy-loading does not hide all meaningful imagery from crawlers or users without JS;
- videos, virtual tours, and maps do not replace essential text facts;
- no avoidable CLS from hero, gallery, cards, banners, or embedded media.

For performance evidence:

- prefer field data from PageSpeed Insights / CrUX when available;
- use Lighthouse lab data when field data is unavailable and label it as lab data;
- track LCP, CLS, and INP for Core Web Vitals;
- report TBT only as a lab proxy for responsiveness when INP is unavailable; never infer INP from TBT;
- compare mobile first because Google mobile-first indexing is the practical SEO baseline;
- connect performance findings to concrete render-blocking CSS/JS, image sizing, caching, font, third-party, layout-shift, or main-thread causes.

## Output Format For Reviews

When reviewing a page, prefer findings in this order:

1. Indexability / robots / canonical / redirect / `hreflang` issues
2. Missing or weak metadata / H1 / schema issues
3. E-E-A-T evidence, trust, real estate accuracy, and content quality issues
4. Programmatic SEO and duplicate/thin-page risks
5. Image/video SEO, CLS, and mobile rendering issues

For GEO or LLM visibility reviews, add an LLM-specific section after normal SEO findings. Include extracted entities, likely AI-answer intents, citation-ready passages, missing evidence, misinterpretation risks, source-map gaps, and visible-content/schema alignment.

Keep findings concrete and page-specific.

## Acceptance Checklist

Before finishing SEO work, verify:

- the affected public pages remain localized for `ru`, `en`, and `th` where applicable;
- no accidental `noindex`, blocked crawl path, wrong canonical, or broken `hreflang` was introduced;
- metadata is server-rendered and page-specific;
- the page has one clear H1;
- schema is truthful, valid, localized, and not over-scoped;
- authorship, business identity, contact paths, freshness, and source/review evidence are visible where the page topic requires them;
- property facts, prices, currencies, locations, and statuses remain consistent with backend data;
- E-E-A-T is demonstrated through original evidence and accurate real estate context, not claimed through badges or boilerplate;
- programmatic pages have distinct user value and are not doorway clones;
- private/admin/AJAX/session endpoints are not made indexable;
- image and media usage does not create avoidable CLS;
- Google AI Search changes remain normal SEO improvements, not AEO/GEO hacks;
- the page reads like a trustworthy Phuket real estate agency page, not a keyword shell.
