# Sample requests

```
curl -X GET "http://localhost:8080/balance?customerPhoneNumber=5566778899"
```


```
curl -X POST -H "Content-Type: application/json" -d '{"user_id": 5566778899, "amount": 1000}' http://localhost:8080/charge
```

