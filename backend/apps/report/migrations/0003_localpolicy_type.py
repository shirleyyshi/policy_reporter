# Generated for LocalPolicy 业务分类字段（财税/税务/金融/产业/综合）

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("report", "0002_centralpolicy_crawled_at_localpolicy_crawled_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="localpolicy",
            name="type",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="业务分类"),
        ),
    ]
