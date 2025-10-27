from rest_framework import serializers


class UpdateRatingSerializer(serializers.Serializer):
    Vehicle_type = serializers.ChoiceField(choices=['Auto', 'Bike', 'Ship', 'Helicopter', 'SpecialTechnic'])
    Vehicle_id = serializers.IntegerField()
    Cleanliness = serializers.IntegerField(min_value=1, max_value=5)
    Maintenance = serializers.IntegerField(min_value=1, max_value=5)
    Communication = serializers.IntegerField(min_value=1, max_value=5)
    Convenience = serializers.IntegerField(min_value=1, max_value=5)
    Accuracy = serializers.IntegerField(min_value=1, max_value=5)
