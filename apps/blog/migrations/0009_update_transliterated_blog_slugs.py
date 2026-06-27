from django.db import migrations


BLOG_SLUG_UPDATES = {
    'chek-list-pokupatelya-nedvizhimosti-v-tailande-chto-proverit-pered-pokupkoj': 'thailand-property-buying-checklist',
    'chestnyj-dialog-na-phukete-kak-agenty-i-zastrojshiki-usilivayut-prozrachnost-rynka': 'honest-dialogue-in-phuket-how-agents-and-developers-enhance-market-transparency',
    '11-lovushek-v-dogovorah-zastrojshikov': 'eleven-traps-in-developers-contracts',
    'all-hands-phuket-real-estate-market-2026-lidery-rynka-phuketa-obsudili-strategiyu-otrasli-na-20252026-gody': 'all-hands-phuket-real-estate-market-2026-phuket-market-leaders-discuss-industry-strategy',
    'investicionnaya-karta-phuketa': 'phuket-investment-map',
    'undersun-estate-glavnye-sobytiya-marta-2026-i-trendy-rynka-nedvizhimosti-phuketa': 'undersun-estate-march-2026-events-and-phuket-real-estate-market-trends',
    'undersun-estate-na-c9-sessions-kak-russkoyazychnoe-soobshestvo-menyaet-pravila-igry-na-rynke-nedvizhimosti-phuketa': 'undersun-estate-at-c9-sessions-russian-speaking-community-changing-phuket-real-estate-market',
    'doma-na-phukete-ot-475-mln-bat-unikalnoe-predlozhenie-ot-top-3-zastrojshika-tailanda': 'homes-in-phuket-from-thb-4-75-million-offer-from-top-thailand-developer',
}


def update_blog_slugs(apps, schema_editor):
    BlogPost = apps.get_model('blog', 'BlogPost')

    for old_slug, new_slug in BLOG_SLUG_UPDATES.items():
        post = BlogPost.objects.filter(slug=old_slug).first()
        if not post:
            continue

        conflict = BlogPost.objects.filter(slug=new_slug).exclude(pk=post.pk).exists()
        if conflict:
            continue

        post.slug = new_slug
        post.save(update_fields=['slug'])


class Migration(migrations.Migration):

    dependencies = [
        ('blog', '0008_blogtranslationjob'),
    ]

    operations = [
        migrations.RunPython(update_blog_slugs, migrations.RunPython.noop),
    ]
