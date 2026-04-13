# Frontend – LifeX Action Pad Configuration Tool

This is the **Angular frontend** for the LifeX Action Pad configuration system.

It provides a clean interface for internal users to:

- Select roles  
- View and edit Action Pad pages  
- Manage buttons and layouts  
- Send updates to the Python backend  
- Prepare configuration for LifeX

The frontend communicates with the backend through `/api/...` routes.

---

## 1. Tech Stack

- Angular 18+
- TypeScript
- RxJS
- Angular Material

---

## 2. Project Structure

A simplified view:

```text
frontend/
  src/
    app/
      action-pad/
        components/
        pages/
        services/
      core/
      shared/
    assets/
    environments/
      environment.ts
      environment.prod.ts
  angular.json
  package.json
  README.md (this file)
```


## 3. Setup

From the `frontend/` directory:

1. Install dependencies:

```bash
npm install
```

2. Start the development server:

```bash
npm run start
# or
ng serve
```

The frontend will run at:

 **http://localhost:4200**

---

## 4. Backend Connection

Make sure the backend is running on:

 ****

The API base URL is configured in:

```
src/environments/environment.ts
```

Example:

```ts
export const environment = {
  production: false,
  apiBaseUrl: '/api'
};
```

For production builds, adjust `environment.prod.ts` accordingly.

---

## 5. Available Pages (Typical)


- **Role Selection Page**  
  Choose a LifeX role to work on.

- **Page List View**  
  Shows all Action Pad pages for that role.

- **Page Editor**  
  Create or edit a page:
  - Name
  - Layout
  - Buttons
  - Order

- **Admin dashboard** (admin users only) with session management and live backend log viewer (/admin/logs)


---

## 6. Mock API Mode

If the backend is unavailable, you can enable mock services:

Example mock service structure:

```
app/action-pad/services/mock/
```

Enable it by switching service providers in your `main.ts` or in a dedicated mock environment:

```ts
export const environment = {
  production: false,
  apiBaseUrl: '',
  useMock: true
};
```

Useful when building UI before the backend is ready.

---

## 7. Build for Production

```bash
npm run build --configuration production
```

Output will be placed in:

```
dist/
```

This build can then be served via Nginx, Docker, or integrated into another hosting environment.

---

## 8. Recommended Workflow

1. Run backend  
2. Run frontend  
3. Select a role  
4. View and edit pages and buttons  
5. Save changes  
6. Test full flow with LifeX

---


