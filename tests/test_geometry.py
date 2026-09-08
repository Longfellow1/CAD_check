from server.demo_data import model_v1, model_v2
from server.geometry import minimum_clearance, directional_distance, orientation_angle

def test_battery_bracket_regresses():
    v1,v2=model_v1(),model_v2()
    assert minimum_clearance(v2.objects['battery'],v2.objects['underbody_bracket']).value < minimum_clearance(v1.objects['battery'],v1.objects['underbody_bracket']).value

def test_directional_ground_distance_positive():
    v1=model_v1()
    assert directional_distance(v1.objects['battery'],v1.objects['ground_ref'],'Z').value > 0

def test_orientation_angle():
    assert orientation_angle(model_v2().objects['motor'],'Z') == 2.2
