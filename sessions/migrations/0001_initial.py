# Generated by Django 5.2.1 on 2025-06-09 16:48

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('patients', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WhatsAppSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(max_length=100, unique=True)),
                ('phone_number', models.CharField(max_length=20)),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('expired', 'Expirée')], default='active', max_length=20)),
                ('last_activity', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='whatsapp_sessions', to='patients.patient')),
            ],
            options={
                'unique_together': {('patient', 'session_id')},
            },
        ),
        migrations.CreateModel(
            name='ConversationLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_message', models.TextField()),
                ('ai_response', models.TextField()),
                ('response_time_ms', models.IntegerField(null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('message_length', models.IntegerField(default=0)),
                ('response_length', models.IntegerField(default=0)),
                ('context_documents_used', models.IntegerField(default=0)),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='conversations', to='whatsapp_sessions.whatsappsession')),
            ],
        ),
    ]
