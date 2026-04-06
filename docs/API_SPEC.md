# API Specification

## Jobs

### Create Job

POST /jobs

Body:

```json
{
"title": "Backend Engineer",
"description": "Python API development",
"requirements": "Flask, SQL"
}
```

---

### List Jobs

GET /jobs

---

### Get Job

GET /jobs/{job_id}

---

### Update Job

PUT /jobs/{job_id}

---

### Delete Job

DELETE /jobs/{job_id}

---

## Applications

### Submit Application

POST /applications

Form Data:

```
job_id
applicant_name
applicant_email
resume (PDF)
```

Response:

```
{
"id": 3,
"filter_status": "pending"
}
```

---

### Get Application

GET /applications/{id}

---

### Get Accepted Applications

GET /jobs/{job_id}/applications