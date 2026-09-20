from shapely.geometry.base import BaseGeometry
def overlaps(a:BaseGeometry,b:BaseGeometry)->bool: return a.intersects(b) and a.intersection(b).area>0
