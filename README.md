# Sportspuff v6 🏟️

A comprehensive sports teams and stadiums database with a modern web interface built with Flask and PostgreSQL.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-blue.svg)](https://www.postgresql.org/)

## 🌟 Features

- **173 Teams** across 6 major leagues (NFL, NBA, MLB, NHL, MLS, WNBA)
- **141 Stadiums** with detailed specifications and capacity information
- **Modern Web Interface** with responsive design using Bootstrap 5
- **League-Specific Design** with unique color schemes for each sport
- **RESTful API** endpoints for programmatic access
- **Logo Integration** with team and league logos
- **Search and Filter** capabilities for teams and stadiums
- **Admin Panel** for database management
- **Auto-Deployment** with GitHub Actions and Ansible

## 🎨 Design Philosophy

The application features a cohesive "Modern Arena" color scheme:

### Core Palette
- **Deep Navy** (#1A2A6C): Main background/header tone
- **Cool Gray** (#E0E0E0): Card and panel backgrounds
- **Electric Red** (#FF3B30): Call-to-action highlights
- **Golden Yellow** (#FFB400): Energetic accents
- **Pure White** (#FFFFFF): Typography clarity

### League-Specific Accents
- **MLB**: Royal Blue (#0E4C92) - Traditional baseball calmness
- **NHL**: Ice Silver (#BFC9CA) with Jet Black (#0A0A0A) - Sleek, professional
- **NBA**: Vibrant Purple (#7028E4) - Energetic and entertainment-forward
- **NFL**: Deep Crimson (#B3001B) - Strength and intensity
- **WNBA**: Bright Orange (#FF6F00) - Contemporary identity and empowerment
- **MLS**: Emerald Green (#2BAE66) - Freshness and field-like energy

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- pip (Python package manager)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/pbertain/sportspuff-v6.git
   cd sportspuff-v6
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up the database:**
   ```bash
   # Create PostgreSQL database
   createdb sportspuff_v6
   
   # Run schema
   psql -d sportspuff_v6 -f database_schema.sql
   
   # Import data
   python import_data.py
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

6. **Access the web interface:**
   - Open http://localhost:5000 in your browser

## 🏗️ Architecture

### Database Schema
- **Teams Table**: Team information, league details, stadium relationships
- **Stadiums Table**: Venue details, capacity, specifications, coordinates
- **Lookup Tables**: Leagues, divisions, conferences for data normalization
- **Relationships**: Teams linked to stadiums via `stadium_id` foreign key

### Technology Stack
- **Backend**: Flask (Python)
- **Database**: PostgreSQL
- **Frontend**: Bootstrap 5, HTML5, CSS3
- **Deployment**: Ansible, systemd, GitHub Actions
- **Data Processing**: Pandas, OpenPyXL

## 📁 Project Structure

```
sportspuff-v6/
├── app.py                    # Flask web application
├── database_schema.sql       # PostgreSQL schema
├── import_data.py            # Data import script
├── create_logo_mapping.py    # Logo mapping utility
├── test_setup.py            # Setup verification tests
├── deploy.sh                # Manual deployment script
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── ansible/                # Ansible deployment configuration
│   ├── inventory
│   ├── group_vars/
│   ├── playbooks/
│   └── roles/
├── .github/workflows/      # CI/CD pipelines
├── templates/              # HTML templates
├── static/css/             # Custom CSS with color scheme
├── logos/                  # Team and league logos
└── README.md              # This file
```

## 🔧 API Endpoints

### Teams API
- `GET /api/teams` - Get all teams with stadium information
- `GET /teams` - Web interface for browsing teams
- `GET /team/<id>` - Detailed team view

### Stadiums API
- `GET /api/stadiums` - Get all stadiums with team counts
- `GET /stadiums` - Web interface for browsing stadiums
- `GET /stadium/<id>` - Detailed stadium view

## 🚀 Deployment

### Manual Deployment
```bash
# Deploy to development
./deploy.sh dev

# Deploy to production
./deploy.sh prod
```

### Automatic Deployment
- Push to `dev` branch → auto-deploys to dev environment (port 34181)
- Push to `main` branch → auto-deploys to prod environment (port 34180)

#### GitHub Secrets Setup
For automatic deployment to work, you need to configure these secrets in your GitHub repository:

1. Go to your repository → Settings → Secrets and variables → Actions
2. Add these repository secrets:
   - `SSH_PRIVATE_KEY_DEV`: Your SSH private key for development deployments
   - `SSH_PRIVATE_KEY_PROD`: Your SSH private key for production deployments

The workflows will use these secrets to authenticate with your server and run deployments.

### Access Points
- **Development**: http://host74.nird.club (via NGINX → port 34181)
- **Production**: http://host74.nird.club (via NGINX → port 34180)

> **Note**: Direct port access is not available. NGINX will be configured to route traffic to the appropriate internal ports.

## 🧪 Testing

Run the setup verification tests:
```bash
python test_setup.py
```

This will verify:
- Database connection
- Table existence
- Data integrity
- Sample queries

## 📊 Data Overview

- **173 Teams** across 6 leagues
- **141 Stadiums** with detailed specifications
- **142 Unique stadium IDs** linking teams to venues
- **5 Teams** without stadium assignments (handled gracefully)

## 🔮 Future Enhancements

### Phase 2: Schedule Integration
- Import game schedules from sports APIs
- Display upcoming games and results
- Team vs team matchup history

### Phase 3: Standings & Stats
- Real-time standings integration
- Player statistics (separate table recommended)
- Team performance metrics

### Phase 4: Advanced Features
- User authentication and favorites
- Push notifications for game updates
- Mobile app integration
- Data visualization and analytics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

For questions or issues:
- Create an issue in this repository
- Check the [deployment summary](DEPLOYMENT_SUMMARY.md) for detailed setup instructions

## 🙏 Acknowledgments

- Sports data sourced from comprehensive team and stadium databases
- Logo assets organized by league for easy integration
- Color scheme inspired by modern sports branding principles
- Built with Flask, PostgreSQL, and Bootstrap for reliability and performance

---

**Ready to explore the world of sports data! 🏆**# Deployment test - duplicate team_id fix applied
