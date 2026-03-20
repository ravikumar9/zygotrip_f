from rest_framework import serializers

from .models import SupportTicket, SupportTicketMessage


class SupportTicketMessageSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.full_name', read_only=True)

    class Meta:
        model = SupportTicketMessage
        fields = ['id', 'author', 'author_name', 'message', 'is_staff_reply', 'created_at']
        read_only_fields = ['id', 'author', 'author_name', 'is_staff_reply', 'created_at']


class SupportTicketSerializer(serializers.ModelSerializer):
    messages = SupportTicketMessageSerializer(many=True, read_only=True)

    class Meta:
        model = SupportTicket
        fields = [
            'id', 'user', 'booking', 'subject', 'description', 'status', 'priority', 'channel',
            'assigned_to', 'resolved_at', 'created_at', 'updated_at', 'messages',
        ]
        read_only_fields = ['id', 'user', 'assigned_to', 'resolved_at', 'created_at', 'updated_at']


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    category = serializers.CharField(required=False, write_only=True)

    class Meta:
        model = SupportTicket
        fields = ['booking', 'subject', 'description', 'priority', 'channel', 'category']

    def create(self, validated_data):
        validated_data.pop('category', None)
        return super().create(validated_data)


class SupportTicketUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportTicket
        fields = ['status', 'priority', 'assigned_to']
