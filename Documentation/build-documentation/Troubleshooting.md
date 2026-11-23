# Troubleshooting

Only issues observed during verification are listed here.

## Host port is already allocated

The default Compose startup reported:

~~~text
Bind for 0.0.0.0:8000 failed: port is already allocated
~~~

Port 8000 was already bound by another Docker Desktop service. The successful Compose smoke check used host ports 8001 and 3001. If the backend host port is changed, also ensure the frontend bundle points at that backend URL; the current Compose file does not pass a custom `VITE_BACKEND_URL` build argument.

## Vite selects a different port

Port 3000 was occupied. Both `npm run dev` and `npm run preview` selected port 3001 and continued to serve the UI and proxy `/api`. Use the URL printed by Vite.

## Node 23 engine warnings

An initial dependency installation using Node 23 completed but printed `EBADENGINE` warnings for locked packages. Repeating the install and checks on Node 22.23.5 completed without those warnings. CI uses Node 20 and Node 22; use one of those versions.
