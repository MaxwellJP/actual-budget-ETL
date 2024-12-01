module.paths.push('/home/actual-project/js/node_modules');
const api = require('@actual-app/api');
const fs = require('fs');
const path = require('path');

(async () => {
    try {
        await api.init({
            dataDir: '/home/actual-project/data/',
            serverURL: process.env.ACTUAL_URL,
            password: process.env.ACTUAL_PASSWORD,
        });

        await api.downloadBudget(process.env.BUDGET_ID, {
            password: process.env.BUDGET_PASSWORD,
        });

        console.log("Data downloaded successfully.");
        await api.shutdown();

    } catch (err) {
        console.error("Error:", err);
    }
})();
