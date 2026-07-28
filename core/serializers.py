from rest_framework.serializers import ModelSerializer, SerializerMethodField
from .models import Status, Module, SubModule


class StatusSerializer(ModelSerializer):
    class Meta:
        model = Status
        fields = [
            'id',
            'title',
            'code',
            'color',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubModuleSerializer(ModelSerializer):
    class Meta:
        model = SubModule
        fields = [
            'id',
            'title',
            'description',
            'url_endpoint',
            'image',
        ]


class ModuleSerializer(ModelSerializer):
    sub_modules = SerializerMethodField()

    class Meta:
        model = Module
        fields = [
            'id',
            'title',
            'description',
            'url_endpoint',
            'image',
            'sub_modules',
        ]

    def get_sub_modules(self, module):
        request = self.context.get('request')
        user = request.user if request else None
        permitted = module.get_permitted_sub_modules(user)
        return SubModuleSerializer(permitted, many=True, context=self.context).data