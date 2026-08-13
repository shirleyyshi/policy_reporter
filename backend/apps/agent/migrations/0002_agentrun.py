# Generated for A2: AgentRun state 持久化表

import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agent', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("run_id", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("status", models.CharField(default='running', max_length=20)),
                ("step", models.IntegerField(default=0)),
                ("task_input", models.JSONField(default=dict)),
                ("state_json", models.JSONField(default=dict)),
                ("summary", models.TextField(blank=True, default='')),
                ("docx_path", models.CharField(blank=True, max_length=500, null=True)),
                ("error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "agent_run",
                "ordering": ["-created_at"],
            },
        ),
    ]
