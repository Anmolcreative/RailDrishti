from kafka import KafkaConsumer
import redis,json
r=redis.Redis(host=chr(108)+chr(111)+chr(99)+chr(97)+chr(108)+chr(104)+chr(111)+chr(115)+chr(116),port=6379,decode_responses=True)
consumer=KafkaConsumer(chr(116)+chr(114)+chr(97)+chr(105)+chr(110)+chr(45)+chr(115)+chr(116)+chr(97)+chr(116)+chr(117)+chr(115),bootstrap_servers=[chr(108)+chr(111)+chr(99)+chr(97)+chr(108)+chr(104)+chr(111)+chr(115)+chr(116)+chr(58)+chr(57)+chr(48)+chr(57)+chr(50)],value_deserializer=lambda x:json.loads(x.decode(chr(117)+chr(116)+chr(102)+chr(45)+chr(56))))
print(chr(82)+chr(101)+chr(100)+chr(105)+chr(115)+chr(32)+chr(115)+chr(116)+chr(97)+chr(114)+chr(116)+chr(101)+chr(100))
for message in consumer:
 data=message.value
 key=chr(116)+chr(114)+chr(97)+chr(105)+chr(110)+chr(58)+data[chr(116)+chr(114)+chr(97)+chr(105)+chr(110)+chr(95)+chr(105)+chr(100)]
 r.setex(key,30,json.dumps(data))
 print(chr(67)+chr(97)+chr(99)+chr(104)+chr(101)+chr(100)+chr(58)+chr(32)+key)
