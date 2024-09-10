from django.db import models
from django.contrib.auth.models import User


class ResumeDetails(models.Model):
    name = models.CharField(max_length= 50 ,null =True)
    institution =models.CharField(max_length = 100,null =True)
    city =models.CharField(max_length= 50,null =True)
    passing_out_year=models.IntegerField(default = 0,null =True)
    Cgpa = models.FloatField(default= 0 ,null =True)
    Degree =models.CharField(max_length= 50,null =True)
    skills = models.CharField(max_length = 200,null =True)
    work_experience = models.CharField(max_length=100,null =True)
    projects = models.CharField(max_length= 100,null =True)
    achievements =models.CharField(max_length= 200,null =True)
    emailid = models.CharField(max_length= 50,null =True)
    phone_number = models.IntegerField(null =True)

class ResumeCheck(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    upload_status = models.IntegerField(default=0)