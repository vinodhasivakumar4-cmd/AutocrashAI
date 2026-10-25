const form = document.getElementById("uploadForm");

form.addEventListener("submit", async function(event) {

    event.preventDefault();

    const formData = new FormData(form);

    document.getElementById("loading").style.display = "block";

    try {

        const response = await fetch("/analyze", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!data.success) {
            alert(data.message);
            return;
        }

        const result = data.result;

        document.getElementById("apkName").textContent =
            result.apk;

        document.getElementById("crashType").textContent =
            result.crash_type;

        document.getElementById("reason").textContent =
            result.reason;

        document.getElementById("trigger").textContent =
            result.trigger;

        document.getElementById("rootCause").textContent =
            result.root_cause;


        const steps = document.getElementById("steps");

        steps.innerHTML = "";

        result.steps.forEach(step => {

            const li = document.createElement("li");

            li.textContent = step;

            steps.appendChild(li);

        });


        document.getElementById("uiAction").textContent =
            result.validation.ui_action;

        document.getElementById("crashTrigger").textContent =
            result.validation.crash_trigger;

        document.getElementById("reproduction").textContent =
            result.validation.reproduction_path;


        document.getElementById("results").style.display =
            "block";

    } catch (error) {

        alert("Something went wrong.");

        console.error(error);

    } finally {

        document.getElementById("loading").style.display =
            "none";
    }

});