from django.db import models
from django.contrib.auth.models import User


class ResumeDetails(models.Model):
    status_choice=(('pending','pending'),('approved','approved'),('rejected','rejected'))
    user =models.ForeignKey(User,on_delete=models.CASCADE ,null=True)
    name = models.CharField(max_length= 50 ,null =True)
    institution =models.CharField(max_length = 100,null =True)
    city =models.CharField(max_length= 50,null =True)
    passing_out_year=models.CharField(max_length=10 ,default = 0,null =True)
    Cgpa = models.FloatField(default= 0 ,null =True)
    Degree =models.CharField(max_length= 50,null =True)
    skills = models.CharField(max_length = 200,null =True)
    work_experience = models.CharField(max_length=100,null =True)
    projects = models.CharField(max_length= 100,null =True)
    achievements =models.CharField(max_length= 200,null =True)
    emailid = models.CharField(max_length= 50,null =True)
    phone_number = models.CharField(max_length=20,null =True)
    score =models.FloatField(default=0)
    tech_skill_score=models.FloatField(default=0)
    exp_achieve_score=models.FloatField(default=0)
    cert_score=models.FloatField(default=0)
    project_score=models.FloatField(default=0)
    status=models.CharField(max_length=20,  choices=status_choice)

class ResumeCheck(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    upload_status = models.IntegerField(default=0)

class FileResumePath(models.Model):
    user = models.ForeignKey(User ,on_delete=models.CASCADE)
    path = models.CharField(max_length=200 , null=True)