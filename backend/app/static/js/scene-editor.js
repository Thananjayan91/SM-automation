/**
 * Scene Editor for Video Text Overlays & Ken Burns Animations.
 * Integrates Fabric.js interactive canvas, template system, and AI suggestions.
 */

window.SceneEditor = (function () {
    let canvas = null;
    let scenes = [];
    let activeSceneIndex = 0;
    let activeTextIndex = -1;
    let availableTemplates = [];
    let currentAspectRatio = "9:16";

    // Canvas display dimensions by aspect ratio
    const CANVAS_DIMS = {
        "9:16": { width: 320, height: 568 },
        "1:1": { width: 400, height: 400 },
        "16:9": { width: 480, height: 270 }
    };

    function init(imageUrls, aspectRatio = "9:16") {
        currentAspectRatio = aspectRatio;
        const dims = CANVAS_DIMS[aspectRatio] || CANVAS_DIMS["9:16"];

        const canvasEl = document.getElementById("scene-fabric-canvas");
        if (!canvasEl) return;

        // Initialize or resize Fabric canvas
        if (!canvas) {
            canvas = new fabric.Canvas("scene-fabric-canvas", {
                width: dims.width,
                height: dims.height,
                selection: true,
                preserveObjectStacking: true
            });

            // Bind Fabric selection events
            canvas.on("selection:created", onObjectSelected);
            canvas.on("selection:updated", onObjectSelected);
            canvas.on("selection:cleared", onSelectionCleared);
            canvas.on("object:modified", onObjectModified);
        } else {
            canvas.setDimensions(dims);
        }

        // Initialize scenes array from image URLs if empty or different
        scenes = imageUrls.map((url, idx) => {
            // Retain existing scene data if index matches
            const existing = scenes[idx];
            if (existing && existing.imageUrl === url) {
                return existing;
            }
            return {
                id: `scene_${idx}`,
                imageUrl: url,
                imageAnimation: "zoom_in",
                textAnimation: "fade_in",
                texts: [
                    {
                        content: idx === 0 ? "HEADLINE HERE" : `POINT #${idx + 1}`,
                        x_percent: 50,
                        y_percent: 45,
                        font_family: "Montserrat",
                        font_size: 38,
                        font_weight: "bold",
                        color: "#FFFFFF",
                        stroke_color: "#000000",
                        stroke_width: 2,
                        shadow: { enabled: true, color: "rgba(0, 0, 0, 0.7)", blur: 8, offsetX: 3, offsetY: 3 },
                        background: { enabled: false, color: "rgba(0, 0, 0, 0.5)", padding: 12, border_radius: 8 },
                        max_width_percent: 85,
                        text_align: "center"
                    }
                ]
            };
        });

        loadTemplates();
        renderSceneTabs();
        loadScene(0);
    }

    async function loadTemplates() {
        try {
            const resp = await fetch("/api/v1/video/templates");
            const data = await resp.json();
            if (data.templates) {
                availableTemplates = data.templates;
                populateTemplateDropdown();
            }
        } catch (err) {
            console.warn("Could not load templates:", err);
        }
    }

    function populateTemplateDropdown() {
        const select = document.getElementById("scene-template-select");
        if (!select) return;
        select.innerHTML = '<option value="">-- Apply a Template Style --</option>';

        const presetGroup = document.createElement("optgroup");
        presetGroup.label = "Preset Styles";
        const customGroup = document.createElement("optgroup");
        customGroup.label = "Custom Saved Templates";

        availableTemplates.forEach((tpl) => {
            const opt = document.createElement("option");
            opt.value = tpl.id;
            opt.textContent = tpl.name;
            if (tpl.is_preset) {
                presetGroup.appendChild(opt);
            } else {
                customGroup.appendChild(opt);
            }
        });

        if (presetGroup.children.length > 0) select.appendChild(presetGroup);
        if (customGroup.children.length > 0) select.appendChild(customGroup);
    }

    function renderSceneTabs() {
        const container = document.getElementById("scene-tabs-container");
        if (!container) return;
        container.innerHTML = "";

        scenes.forEach((sc, idx) => {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `btn btn-sm ${idx === activeSceneIndex ? "btn-primary shadow-sm" : "btn-outline-secondary"} position-relative`;
            btn.innerHTML = `<i class="bi bi-image me-1"></i> Scene ${idx + 1}`;
            btn.onclick = () => switchScene(idx);
            container.appendChild(btn);
        });
    }

    function switchScene(idx) {
        if (idx < 0 || idx >= scenes.length) return;
        syncCanvasToState();
        activeSceneIndex = idx;
        renderSceneTabs();
        loadScene(idx);
    }

    function loadScene(idx) {
        const scene = scenes[idx];
        if (!scene || !canvas) return;

        canvas.clear();
        activeTextIndex = -1;

        // Set Scene Animation controls
        const imgAnimSelect = document.getElementById("scene-image-anim");
        if (imgAnimSelect) imgAnimSelect.value = scene.imageAnimation || "zoom_in";

        const textAnimSelect = document.getElementById("scene-text-anim");
        if (textAnimSelect) textAnimSelect.value = scene.textAnimation || "fade_in";

        // Load background image
        const dims = CANVAS_DIMS[currentAspectRatio] || CANVAS_DIMS["9:16"];
        fabric.Image.fromURL(
            scene.imageUrl,
            function (img) {
                if (!img) return;
                // Scale to cover
                const scale = Math.max(dims.width / img.width, dims.height / img.height);
                img.set({
                    originX: "center",
                    originY: "center",
                    left: dims.width / 2,
                    top: dims.height / 2,
                    scaleX: scale,
                    scaleY: scale,
                    selectable: false,
                    evented: false
                });
                canvas.setBackgroundImage(img, canvas.renderAll.bind(canvas));

                // Load text objects
                loadTextsToCanvas(scene.texts);
            },
            { crossOrigin: "anonymous" }
        );
    }

    function loadTextsToCanvas(texts) {
        const dims = CANVAS_DIMS[currentAspectRatio] || CANVAS_DIMS["9:16"];

        texts.forEach((item, tIdx) => {
            const x = (item.x_percent / 100.0) * dims.width;
            const y = (item.y_percent / 100.0) * dims.height;
            const displaySize = Math.max(14, Math.round(item.font_size * (dims.width / 720.0)));

            const textbox = new fabric.Textbox(item.content || "", {
                left: x,
                top: y,
                originX: "center",
                originY: "center",
                width: (item.max_width_percent / 100.0) * dims.width,
                textAlign: item.text_align || "center",
                fontFamily: item.font_family || "Montserrat",
                fontSize: displaySize,
                fontWeight: item.font_weight || "bold",
                fill: item.color || "#FFFFFF",
                stroke: item.stroke_color || "#000000",
                strokeWidth: item.stroke_width || 0,
                cornerColor: "#0d6efd",
                cornerStyle: "circle",
                transparentCorners: false,
                borderColor: "#0d6efd"
            });

            if (item.shadow && item.shadow.enabled) {
                textbox.set(
                    "shadow",
                    new fabric.Shadow({
                        color: item.shadow.color || "rgba(0,0,0,0.7)",
                        blur: item.shadow.blur || 6,
                        offsetX: item.shadow.offsetX || 2,
                        offsetY: item.shadow.offsetY || 2
                    })
                );
            }

            if (item.background && item.background.enabled) {
                textbox.set("backgroundColor", item.background.color || "rgba(0,0,0,0.5)");
            }

            textbox.sceneTextIndex = tIdx;
            canvas.add(textbox);

            if (tIdx === 0) {
                canvas.setActiveObject(textbox);
                activeTextIndex = 0;
                populateControlsFromText(item);
            }
        });

        canvas.renderAll();
    }

    function onObjectSelected(e) {
        const obj = e.selected ? e.selected[0] : null;
        if (!obj || obj.type !== "textbox") return;
        activeTextIndex = obj.sceneTextIndex !== undefined ? obj.sceneTextIndex : 0;
        const curScene = scenes[activeSceneIndex];
        if (curScene && curScene.texts[activeTextIndex]) {
            populateControlsFromText(curScene.texts[activeTextIndex]);
        }
    }

    function onSelectionCleared() {
        activeTextIndex = -1;
    }

    function onObjectModified(e) {
        const obj = e.target;
        if (!obj || obj.sceneTextIndex === undefined) return;
        const dims = CANVAS_DIMS[currentAspectRatio] || CANVAS_DIMS["9:16"];
        const curScene = scenes[activeSceneIndex];
        if (!curScene) return;

        const item = curScene.texts[obj.sceneTextIndex];
        if (!item) return;

        // Update percentage coordinates
        item.x_percent = Math.round((obj.left / dims.width) * 100);
        item.y_percent = Math.round((obj.top / dims.height) * 100);
        item.content = obj.text;
    }

    function syncCanvasToState() {
        const curScene = scenes[activeSceneIndex];
        if (!curScene || !canvas) return;

        // Image & text animations
        const imgAnim = document.getElementById("scene-image-anim");
        if (imgAnim) curScene.imageAnimation = imgAnim.value;
        const textAnim = document.getElementById("scene-text-anim");
        if (textAnim) curScene.textAnimation = textAnim.value;

        // Sync text inputs
        if (activeTextIndex >= 0 && curScene.texts[activeTextIndex]) {
            pullControlsIntoText(curScene.texts[activeTextIndex]);
        }
    }

    function populateControlsFromText(item) {
        if (!item) return;
        setVal("text-content-input", item.content || "");
        setVal("text-font-family", item.font_family || "Montserrat");
        setVal("text-font-size", item.font_size || 42);
        setVal("text-font-weight", item.font_weight || "bold");
        setVal("text-color", item.color || "#FFFFFF");
        setVal("text-stroke-color", item.stroke_color || "#000000");
        setVal("text-stroke-width", item.stroke_width || 0);

        const sh = item.shadow || {};
        setChecked("text-shadow-enabled", !!sh.enabled);
        setVal("text-shadow-color", sh.color || "rgba(0,0,0,0.7)");
        setVal("text-shadow-blur", sh.blur || 6);

        const bg = item.background || {};
        setChecked("text-bg-enabled", !!bg.enabled);
        setVal("text-bg-color", bg.color || "rgba(0,0,0,0.5)");
        setVal("text-bg-padding", bg.padding || 12);
        setVal("text-bg-radius", bg.border_radius || 8);
    }

    function pullControlsIntoText(item) {
        if (!item) return;
        item.content = getVal("text-content-input");
        item.font_family = getVal("text-font-family");
        item.font_size = parseInt(getVal("text-font-size"), 10) || 42;
        item.font_weight = getVal("text-font-weight");
        item.color = getVal("text-color");
        item.stroke_color = getVal("text-stroke-color");
        item.stroke_width = parseInt(getVal("text-stroke-width"), 10) || 0;

        item.shadow = {
            enabled: getChecked("text-shadow-enabled"),
            color: getVal("text-shadow-color"),
            blur: parseInt(getVal("text-shadow-blur"), 10) || 6,
            offsetX: 2,
            offsetY: 2
        };

        item.background = {
            enabled: getChecked("text-bg-enabled"),
            color: getVal("text-bg-color"),
            padding: parseInt(getVal("text-bg-padding"), 10) || 12,
            border_radius: parseInt(getVal("text-bg-radius"), 10) || 8
        };
    }

    function updateActiveTextFromControls() {
        const curScene = scenes[activeSceneIndex];
        if (!curScene || activeTextIndex < 0 || !curScene.texts[activeTextIndex]) return;

        const item = curScene.texts[activeTextIndex];
        pullControlsIntoText(item);

        const activeObj = canvas ? canvas.getActiveObject() : null;
        if (activeObj && activeObj.type === "textbox") {
            const dims = CANVAS_DIMS[currentAspectRatio] || CANVAS_DIMS["9:16"];
            const displaySize = Math.max(14, Math.round(item.font_size * (dims.width / 720.0)));

            activeObj.set({
                text: item.content,
                fontFamily: item.font_family,
                fontSize: displaySize,
                fontWeight: item.font_weight,
                fill: item.color,
                stroke: item.stroke_color,
                strokeWidth: item.stroke_width
            });

            if (item.shadow && item.shadow.enabled) {
                activeObj.set(
                    "shadow",
                    new fabric.Shadow({
                        color: item.shadow.color,
                        blur: item.shadow.blur,
                        offsetX: 2,
                        offsetY: 2
                    })
                );
            } else {
                activeObj.set("shadow", null);
            }

            activeObj.set("backgroundColor", item.background && item.background.enabled ? item.background.color : "");
            canvas.renderAll();
        }
    }

    function addText() {
        const curScene = scenes[activeSceneIndex];
        if (!curScene) return;

        const newText = {
            content: "NEW CAPTION",
            x_percent: 50,
            y_percent: curScene.texts.length === 0 ? 50 : 75,
            font_family: "Montserrat",
            font_size: 34,
            font_weight: "bold",
            color: "#FFD700",
            stroke_color: "#000000",
            stroke_width: 2,
            shadow: { enabled: true, color: "rgba(0,0,0,0.7)", blur: 6, offsetX: 2, offsetY: 2 },
            background: { enabled: false, color: "rgba(0,0,0,0.5)", padding: 10, border_radius: 6 },
            max_width_percent: 85,
            text_align: "center"
        };

        curScene.texts.push(newText);
        loadScene(activeSceneIndex);
    }

    function deleteActiveText() {
        const curScene = scenes[activeSceneIndex];
        if (!curScene || activeTextIndex < 0) return;

        curScene.texts.splice(activeTextIndex, 1);
        activeTextIndex = curScene.texts.length > 0 ? 0 : -1;
        loadScene(activeSceneIndex);
    }

    function applyTemplateToCurrent(templateId) {
        if (!templateId) return;
        const tpl = availableTemplates.find((t) => t.id === templateId);
        if (!tpl || !tpl.config) return;

        const cfg = tpl.config;
        const curScene = scenes[activeSceneIndex];
        if (!curScene) return;

        if (cfg.image_animation) curScene.imageAnimation = cfg.image_animation;
        if (cfg.text_animation) curScene.textAnimation = cfg.text_animation;

        if (activeTextIndex >= 0 && curScene.texts[activeTextIndex]) {
            const item = curScene.texts[activeTextIndex];
            if (cfg.font_family) item.font_family = cfg.font_family;
            if (cfg.font_size) item.font_size = cfg.font_size;
            if (cfg.font_weight) item.font_weight = cfg.font_weight;
            if (cfg.color) item.color = cfg.color;
            if (cfg.stroke_color !== undefined) item.stroke_color = cfg.stroke_color;
            if (cfg.stroke_width !== undefined) item.stroke_width = cfg.stroke_width;
            if (cfg.shadow) item.shadow = { ...cfg.shadow };
            if (cfg.background) item.background = { ...cfg.background };

            populateControlsFromText(item);
            updateActiveTextFromControls();
        }
    }

    function applyTemplateToAllScenes() {
        const select = document.getElementById("scene-template-select");
        const tplId = select ? select.value : "";
        if (!tplId) {
            alert("Please select a template first.");
            return;
        }

        const tpl = availableTemplates.find((t) => t.id === tplId);
        if (!tpl || !tpl.config) return;
        const cfg = tpl.config;

        scenes.forEach((sc) => {
            if (cfg.image_animation) sc.imageAnimation = cfg.image_animation;
            if (cfg.text_animation) sc.textAnimation = cfg.text_animation;
            sc.texts.forEach((item) => {
                if (cfg.font_family) item.font_family = cfg.font_family;
                if (cfg.font_size) item.font_size = cfg.font_size;
                if (cfg.font_weight) item.font_weight = cfg.font_weight;
                if (cfg.color) item.color = cfg.color;
                if (cfg.stroke_color !== undefined) item.stroke_color = cfg.stroke_color;
                if (cfg.stroke_width !== undefined) item.stroke_width = cfg.stroke_width;
                if (cfg.shadow) item.shadow = { ...cfg.shadow };
                if (cfg.background) item.background = { ...cfg.background };
            });
        });

        loadScene(activeSceneIndex);
        alert(`Applied template "${tpl.name}" to all ${scenes.length} scenes.`);
    }

    async function autoSuggestText() {
        const topic = document.getElementById("video-topic") ? document.getElementById("video-topic").value.trim() : "";
        if (!topic) {
            alert("Please enter a topic in Step 1 first.");
            return;
        }

        const langRadio = document.querySelector('input[name="video-lang"]:checked');
        const language = langRadio ? langRadio.value : "english";
        const btn = document.getElementById("btn-auto-suggest-text");
        if (btn) btn.disabled = true;

        try {
            const resp = await fetch("/api/v1/video/suggest-texts", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    topic,
                    scene_number: activeSceneIndex + 1,
                    total_scenes: scenes.length,
                    language
                })
            });
            const data = await resp.json();
            if (data.suggestions && data.suggestions.length > 0) {
                // Populate the text input with the first punchy suggestion
                const suggested = data.suggestions[0];
                setVal("text-content-input", suggested);
                updateActiveTextFromControls();
            }
        } catch (err) {
            alert("Could not fetch AI text suggestions.");
        } finally {
            if (btn) btn.disabled = false;
        }
    }

    async function saveCurrentAsTemplate() {
        const name = prompt("Enter a name for your custom styling template:", "My Brand Style");
        if (!name || !name.trim()) return;

        const curScene = scenes[activeSceneIndex];
        const activeText = curScene && activeTextIndex >= 0 ? curScene.texts[activeTextIndex] : null;
        if (!activeText) {
            alert("No text selected to save style from.");
            return;
        }

        const config = {
            font_family: activeText.font_family,
            font_size: activeText.font_size,
            font_weight: activeText.font_weight,
            color: activeText.color,
            stroke_color: activeText.stroke_color,
            stroke_width: activeText.stroke_width,
            shadow: activeText.shadow,
            background: activeText.background,
            image_animation: curScene.imageAnimation || "zoom_in",
            text_animation: curScene.textAnimation || "fade_in"
        };

        try {
            const resp = await fetch("/api/v1/video/templates", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name: name.trim(), config })
            });
            const data = await resp.json();
            if (resp.ok && data.template) {
                alert(`Template "${name}" saved successfully!`);
                await loadTemplates();
                const select = document.getElementById("scene-template-select");
                if (select) select.value = data.template.id;
            } else {
                alert(data.message || "Failed to save template.");
            }
        } catch (err) {
            alert("Network error saving template.");
        }
    }

    function exportScenes() {
        syncCanvasToState();
        return scenes.map((sc) => ({
            image_url: sc.imageUrl,
            image_animation: sc.imageAnimation || "zoom_in",
            text_animation: sc.textAnimation || "fade_in",
            texts: sc.texts || []
        }));
    }

    // Helper utilities
    function setVal(id, val) {
        const el = document.getElementById(id);
        if (el) el.value = val;
    }
    function getVal(id) {
        const el = document.getElementById(id);
        return el ? el.value : "";
    }
    function setChecked(id, val) {
        const el = document.getElementById(id);
        if (el) el.checked = val;
    }
    function getChecked(id) {
        const el = document.getElementById(id);
        return el ? el.checked : false;
    }

    return {
        init,
        switchScene,
        addText,
        deleteActiveText,
        updateActiveTextFromControls,
        applyTemplateToCurrent,
        applyTemplateToAllScenes,
        autoSuggestText,
        saveCurrentAsTemplate,
        exportScenes
    };
})();
