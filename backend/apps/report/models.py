from django.db import models


class CentralPolicy(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=500)
    content = models.TextField()
    type = models.CharField(max_length=100)
    publish_time = models.DateTimeField()
    source_url = models.URLField(max_length=1000, blank=True)
    crawled_at = models.DateTimeField(null=True, blank=True, verbose_name="采集时间")

    class Meta:
        db_table = 'central_policies'
        ordering = ['-publish_time']

    def __str__(self):
        return self.title


class LocalPolicy(models.Model):
    id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=500)
    content = models.TextField()
    province = models.CharField(max_length=100)
    publish_time = models.DateTimeField()
    source_url = models.URLField(max_length=1000, blank=True)
    crawled_at = models.DateTimeField(null=True, blank=True, verbose_name="采集时间")

    class Meta:
        db_table = 'local_policies'
        ordering = ['-publish_time']

    def __str__(self):
        return self.title
