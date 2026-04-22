import traceback
from inference import predict_session

try:
    print(predict_session('Mumbai Indians', 'Royal Challengers Bengaluru', 90, 0, 8.2))
except Exception as e:
    traceback.print_exc()
