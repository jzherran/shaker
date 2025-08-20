## 🚀 Add Collaborative Funding Financial Movements System

### Description
This PR introduces a comprehensive financial movements system for collaborative funding. The system allows administrators to manage contributions and provides clients with real-time account status and balance information.

### Key Features
- **FastAPI-based REST API** with automatic documentation
- **AWS DynamoDB integration** for scalable data storage
- **Vercel-ready deployment** configuration
- **Admin API endpoints** with API key authentication
- **Real-time balance calculation** and account summaries

### Architecture Highlights
- **Serverless deployment** using Vercel and AWS Lambda
- **NoSQL data model** optimized for financial transactions
- **Secure API design** with authentication middleware
- **CORS-enabled** for cross-origin requests

### Changes Made
- ✅ Created FastAPI application structure
- ✅ Implemented DynamoDB client for data persistence
- ✅ Added movement and account models with validation
- ✅ Created admin endpoints for movement creation
- ✅ Implemented client endpoints for account queries
- ✅ Added Vercel deployment configuration
- ✅ Created setup scripts for AWS infrastructure
- ✅ Added comprehensive documentation with diagrams

### Testing
- [ ] Local development server tested
- [ ] DynamoDB table creation verified
- [ ] API endpoints manually tested
- [ ] Authentication flow validated

### Deployment Steps
1. Configure AWS credentials
2. Run `python scripts/create_tables.py`
3. Set up Vercel environment variables
4. Deploy with `vercel --prod`

### Documentation
- Added detailed README with Mermaid diagrams
- Included API endpoint documentation
- Provided setup and deployment instructions

### Related Issues
- Addresses need for collaborative funding tracking
- Implements admin contribution management
- Provides client account visibility

/cc @jzherran