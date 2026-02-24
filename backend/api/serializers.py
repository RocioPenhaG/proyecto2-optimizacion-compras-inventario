from django.contrib.auth.models import Group, User
from rest_framework import serializers

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]

class RoleAssignSerializer(serializers.Serializer):
    username = serializers.CharField()
    role = serializers.CharField()

    def validate(self, data):
        if not User.objects.filter(username=data["username"]).exists():
            raise serializers.ValidationError("El usuario no existe.")
        if not Group.objects.filter(name=data["role"]).exists():
            raise serializers.ValidationError("El rol no existe.")
        return data
