# Deployment Guide

Complete guide for deploying the LLM Quiz Solver to production.

## 🌐 Deployment Options

### Option 1: Railway (Recommended)

Railway provides easy deployment with automatic HTTPS.

#### Steps:

1. **Sign up**: Visit [railway.app](https://railway.app)

2. **Create New Project**:
   ```bash
   # Connect your GitHub repo
   # Railway will auto-detect Python
   ```

3. **Add Environment Variables**:
   - `STUDENT_EMAIL`
   - `STUDENT_SECRET`
   - `GEMINI_API_KEY` (optional)
   - `OPENAI_API_KEY` (optional)

4. **Configure Start Command**:
   ```
   uvicorn app:app --host 0.0.0.0 --port $PORT
   ```

5. **Deploy**: Push to main branch, Railway auto-deploys

6. **Get URL**: Railway provides HTTPS URL like `https://your-app.railway.app`

### Option 2: Render

Free tier available with automatic HTTPS.

#### Steps:

1. **Sign up**: [render.com](https://render.com)

2. **Create Web Service**:
   - Connect GitHub repo
   - Environment: Python 3.11
   - Build Command: `pip install -r requirements.txt && playwright install chromium`
   - Start Command: `uvicorn app:app --host 0.0.0.0 --port $PORT`

3. **Add Environment Variables** in Render dashboard

4. **Deploy**: Automatic on push

### Option 3: Heroku

Classic PaaS option.

#### Steps:

1. **Install Heroku CLI**:
   ```bash
   curl https://cli-assets.heroku.com/install.sh | sh
   ```

2. **Login**:
   ```bash
   heroku login
   ```

3. **Create Procfile**:
   ```
   web: uvicorn app:app --host 0.0.0.0 --port $PORT
   ```

4. **Create runtime.txt**:
   ```
   python-3.11.7
   ```

5. **Deploy**:
   ```bash
   heroku create your-app-name
   heroku config:set STUDENT_EMAIL=your@email.com
   heroku config:set STUDENT_SECRET=your_secret
   heroku buildpacks:add heroku/python
   heroku buildpacks:add https://github.com/mxschmitt/heroku-playwright-buildpack.git
   git push heroku main
   ```

### Option 4: Google Cloud Run

Serverless container deployment.

#### Steps:

1. **Create Dockerfile**:
   ```dockerfile
   FROM python:3.11-slim

   WORKDIR /app

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       wget \
       gnupg \
       && rm -rf /var/lib/apt/lists/*

   # Copy requirements
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Install Playwright
   RUN playwright install chromium
   RUN playwright install-deps chromium

   # Copy application
   COPY . .

   # Run app
   CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
   ```

2. **Deploy**:
   ```bash
   gcloud run deploy llm-quiz-solver \
     --source . \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars STUDENT_EMAIL=your@email.com,STUDENT_SECRET=your_secret
   ```

### Option 5: AWS EC2

Traditional VPS hosting.

#### Steps:

1. **Launch EC2 Instance**:
   - Ubuntu 22.04
   - t2.medium or larger
   - Open port 8000

2. **SSH and Setup**:
   ```bash
   ssh -i your-key.pem ubuntu@your-ec2-ip

   # Update system
   sudo apt update && sudo apt upgrade -y

   # Install Python
   sudo apt install python3.11 python3-pip -y

   # Clone repo
   git clone https://github.com/yourusername/llm-quiz-solver.git
   cd llm-quiz-solver

   # Install dependencies
   pip3 install -r requirements.txt
   playwright install chromium
   sudo playwright install-deps chromium

   # Setup .env
   nano .env
   # Add your credentials

   # Run with nohup
   nohup python3 app.py > server.log 2>&1 &
   ```

3. **Setup Nginx (optional)**:
   ```bash
   sudo apt install nginx -y
   
   # Configure reverse proxy
   sudo nano /etc/nginx/sites-available/quiz-solver
   ```

   ```nginx
   server {
       listen 80;
       server_name your-domain.com;

       location / {
           proxy_pass http://127.0.0.1:8000;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
       }
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/quiz-solver /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

4. **Setup SSL with Let's Encrypt**:
   ```bash
   sudo apt install certbot python3-certbot-nginx -y
   sudo certbot --nginx -d your-domain.com
   ```

## 🔐 Security Checklist

- [ ] Environment variables not committed to Git
- [ ] `.env` in `.gitignore`
- [ ] HTTPS enabled (not HTTP)
- [ ] Secrets rotation capability
- [ ] Rate limiting configured
- [ ] CORS properly configured
- [ ] Input validation on all endpoints
- [ ] Logging sensitive data avoided

## 📊 Monitoring

### Add Health Checks

The API includes `/health` endpoint. Configure monitoring:

**UptimeRobot** (Free):
1. Add monitor: `https://your-domain.com/health`
2. Check interval: 5 minutes
3. Alert via email

**Railway/Render**: Built-in monitoring

### Logging

View logs:

```bash
# Railway
railway logs

# Render
# Via dashboard

# Heroku
heroku logs --tail

# EC2
tail -f server.log
```

## 🚀 Pre-Quiz Deployment Checklist

**48 Hours Before**:
- [ ] Deploy to production
- [ ] Test with demo endpoint
- [ ] Verify environment variables
- [ ] Check logs are working
- [ ] Confirm HTTPS is active
- [ ] Test from external network

**24 Hours Before**:
- [ ] Submit API URL to Google Form
- [ ] Verify GitHub repo is public
- [ ] Add MIT LICENSE file
- [ ] Update README with deployment URL
- [ ] Test authentication (invalid secret → 403)
- [ ] Test malformed JSON (→ 400)

**12 Hours Before**:
- [ ] Monitor service uptime
- [ ] Check API response times
- [ ] Verify Playwright is working
- [ ] Test quiz chain handling
- [ ] Backup deployment ready

**1 Hour Before** (2:00 PM IST):
- [ ] Monitor dashboard open
- [ ] Logs streaming
- [ ] Service health confirmed
- [ ] No recent code changes
- [ ] Backup plan ready

## 🆘 Backup Plan

If primary deployment fails:

1. **Quick Deploy to Render**:
   ```bash
   # Render allows quick deploy from GitHub
   # Just connect repo and deploy
   ```

2. **Local Ngrok** (Last Resort):
   ```bash
   # Install ngrok
   brew install ngrok  # or download from ngrok.com

   # Run server locally
   python app.py &

   # Expose via ngrok
   ngrok http 8000

   # Use the ngrok HTTPS URL
   ```

## 🐛 Troubleshooting Production Issues

### Server Not Responding

```bash
# Check if process is running
ps aux | grep python

# Check port binding
netstat -tlnp | grep 8000

# Restart service
# (method depends on deployment platform)
```

### Playwright Issues

```bash
# Reinstall browsers
playwright install chromium

# On Linux, install dependencies
sudo apt-get install -y libgbm1 libnss3 libxss1 libasound2
```

### Memory Issues

```bash
# Check memory usage
free -h

# Increase swap (EC2)
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Timeout Issues

Increase timeouts in code:
```python
# In quiz_solver.py
timeout=60000  # Increase from 30000
```

## 📱 Mobile Testing

Test your API from mobile:

```bash
# Use curl from phone's terminal app
curl -X POST https://your-api.com/quiz \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","secret":"test","url":"https://tds-llm-analysis.s-anand.net/demo"}'
```

## 💰 Cost Estimates

| Platform | Free Tier | Paid (Estimated) |
|----------|-----------|------------------|
| Railway | 500 hours/month | $5-10/month |
| Render | 750 hours/month | $7/month |
| Heroku | Dyno sleep after 30 min | $7/month |
| Google Cloud Run | 2M requests/month | Pay per use |
| AWS EC2 | 750 hours (12 months) | $10-20/month |

## 🎯 Production URL Format

Ensure your URL is HTTPS:

✅ Good:
- `https://llm-quiz-solver.railway.app`
- `https://quiz.yourdomain.com`
- `https://llm-quiz-abc123.onrender.com`

❌ Bad:
- `http://...` (not HTTPS)
- `localhost:8000`
- `192.168.1.1:8000`

## 📋 Final Submission

Submit to Google Form:
1. **Email**: your@email.com
2. **Secret**: your_secret_string
3. **System Prompt**: (100 chars)
4. **User Prompt**: (100 chars)
5. **API Endpoint**: https://your-domain.com/quiz
6. **GitHub Repo**: https://github.com/user/repo

---

**You're ready for the quiz! Good luck! 🎉**