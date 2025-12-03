
# NazarethQMS

NazarethQMS is a Django-powered Queue Management System developed as a part of my academic journey in software development. It is designed to streamline hospital queues, processes and promote data-driven decision-making.

## Project Vision

This system was built to demonstrate how web technologies like Django, SQLite, and semantic HTML5 can be used to create scalable, maintainable solutions for hospital queue management. 

##  Features

-  Modular Django architecture
- SQLite database integration
-  Role-based access control (Admin, Receptionist, Doctor)
- Semantic HTML5 and accessible design
- Africa's Talking SMS API integration
- Safaricom Daraja STK Push notification API
-  Organized project structure for maintainability

##  Tech Stack

| Technology   | Purpose                          |
|--------------|----------------------------------|
| Python       | Backend logic (Django framework) |
| SQLite       | Lightweight database             |
| HTML/CSS     | Frontend structure and styling   |
| JavaScript   | Interactivity                    |
| PowerShell   | Utility scripts (if applicable)  |
| C            | Minor components (if applicable) |

##  Project Structure

```
NazarethQMS/
├── Nazareth/            
├── NazarethQMS/          
├── db.sqlite3            
├── manage.py             
└── .idea/                
```

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/Flora72/NazarethQMS.git
   cd NazarethQMS
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the server**
   ```bash
   python3 manage.py runserver
   ```

## Implemented Modules
- User authentication and role management Secure login system with differentiated access for admins, receptionist, and patients.
- Quality metrics dashboard Real-time insights into hospital performance, queue efficiency, and service ratings.
- RESTful APIs for integration Seamless communication with external systems and mobile platforms.
- Unit and integration tests Automated testing to ensure reliability and maintainability.

## Future Enhancements
- [ ] Migrate from SQLite to PostgreSQL or MySQL for production scalability  
- [ ] Deploy on platforms like Heroku, Render, or AWS  
- [ ] Build a mobile-friendly frontend or companion app  
- [ ] Add multilingual support for broader accessibility  



