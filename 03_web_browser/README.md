# Job Application Tracking Dashboard

A comprehensive web-based dashboard to track your AI-powered job application pipeline.

## 🎯 Features

### 📊 **Dashboard Overview**
- **Real-time Statistics**: Total jobs, average score, resumes generated
- **Job Cards**: Visual tiles for each job opening with key information
- **Smart Filtering**: Filter by score ranges, source, resume availability
- **Search Functionality**: Search jobs by title, company, or location

### 📋 **Job Details**
- **Complete Information**: Job title, company, location, experience required
- **Match Scores**: AI-generated compatibility scores (1-100)
- **Apply Links**: Direct links to job applications
- **Resume Downloads**: Download tailored resumes when available

### 📄 **Resume Integration**
- **AI-Generated Resumes**: Tailored resumes for each job opportunity
- **PDF Downloads**: Direct download links for generated resumes
- **Status Tracking**: See which jobs have ready-to-use resumes

## 🏗️ Architecture

### **Backend (Flask)**
- **Database Integration**: SQLite database (`jobs_new.db`)
- **REST API**: Endpoints for jobs, stats, and resume downloads
- **File Management**: Resume PDF detection and serving

### **Frontend (Bootstrap 5)**
- **Responsive Design**: Works on desktop and mobile
- **Modern UI**: Gradient backgrounds, smooth animations
- **Interactive Elements**: Real-time filtering and search

## 📁 File Structure

```
03_web_browser/
├── app.py                 # Flask backend application
├── requirements.txt       # Python dependencies
├── README.md             # This file
└── templates/
    ├── index.html        # Main dashboard
    └── job_detail.html   # Job details page
```

## 🚀 Getting Started

### **1. Install Dependencies**
```bash
cd 03_web_browser
pip install -r requirements.txt
```

### **2. Start the Server**
```bash
python app.py
```

### **3. Access the Dashboard**
Open your browser and navigate to:
```
http://localhost:5000
```

## 🔧 Configuration

### **Database Path**
The app expects the SQLite database at:
```
/home/dinesh/HERMES/08_job_application_pipeline/jobs_new.db
```

### **Resume Path**
Generated resumes are expected in:
```
/home/dinesh/HERMES/08_job_application_pipeline/02_resume_engine/LLM_COMPILED_PDFS/
```

## 📊 API Endpoints

### **GET /api/jobs**
Returns all job postings with resume status.

### **GET /api/job/<job_id>**
Returns detailed information for a specific job.

### **GET /api/stats**
Returns dashboard statistics.

### **GET /download/resume/<filename>**
Downloads a generated resume PDF.

## 🎨 Features in Detail

### **Score Visualization**
- **90-100**: Excellent match (Green)
- **80-89**: Good match (Yellow)  
- **0-79**: Low match (Red)

### **Filtering Options**
- **Score Range**: Filter by match score
- **Source**: Telegram, Gmail, etc.
- **Resume Status**: With/without generated resumes
- **Search**: Real-time search across job details

### **Job Cards Display**
- Company logo (first letter)
- Job title and company name
- Location and experience requirements
- Match score badge
- Resume availability indicator
- Apply and download buttons

## 🔍 Database Schema

The dashboard reads from the `job_postings` table with these key columns:

- `job_unique_id`: Unique job identifier
- `job_title`: Position title
- `company_name`: Company name
- `location`: Job location
- `experience_required`: Required experience
- `score`: AI-generated match score (1-100)
- `apply_url`: Application link
- `source`: Job source (Telegram, Gmail)
- `job_description`: Detailed job description
- `external_job_id`: External job identifier

## 📝 Notes

### **Resume Detection**
The app automatically detects generated resumes by searching for PDF files with naming patterns like:
- `{job_title}_{company_name}.pdf`
- `{job_title}_{company_name}.pdf` (with spaces replaced by underscores)

### **Performance**
- Efficient database queries with connection pooling
- Lazy loading of job details
- Optimized search and filtering

### **Security**
- File path validation for resume downloads
- SQL injection prevention with parameterized queries
- Input sanitization for search and filters

## 🐛 Troubleshooting

### **Dashboard Not Loading**
- Check if the Flask server is running on port 5000
- Verify the database path exists and is accessible
- Check console for JavaScript errors

### **Resumes Not Showing**
- Verify resume PDFs exist in the expected folders
- Check file naming conventions
- Ensure file permissions allow reading

### **Database Issues**
- Verify SQLite database exists at the expected path
- Check if the `job_postings` table exists
- Verify data integrity and column names

## 🔄 Integration with Pipeline

This dashboard integrates seamlessly with your job application pipeline:

1. **Job Sourcing** (`01_job_sourcing/`) → Jobs stored in database
2. **Job Scoring** (`02_job_filtering/`) → AI generates match scores  
3. **Resume Generation** (`02_resume_engine/`) → Tailored resumes created
4. **Dashboard** (`03_web_browser/`) → Visualize and track everything

## 🎯 Future Enhancements

- **Job Application Tracking**: Track application status and responses
- **Resume Analytics**: Views and downloads per resume
- **Email Integration**: Direct application from dashboard
- **Mobile App**: Native mobile application
- **Export Features**: Export job data to CSV/Excel
- **Notifications**: Email alerts for high-score jobs

---

Built with ❤️ using Flask, Bootstrap 5, and FontAwesome icons.
