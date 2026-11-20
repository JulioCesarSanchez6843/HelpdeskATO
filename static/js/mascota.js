(function () {
    var raiz = document.getElementById("mascota-viva");
    if (!raiz) {
        return;
    }

    var escena = raiz.querySelector(".mascota-escena");
    var capas = [raiz.querySelector(".mascota-capa-a"), raiz.querySelector(".mascota-capa-b")];
    var globo = raiz.querySelector(".mascota-globo");
    var textoGlobo = raiz.querySelector(".mascota-globo-texto");

    var base = raiz.dataset.base;
    var nombre = raiz.dataset.nombre || "";
    var saludo = raiz.dataset.saludo || "Hola";
    var vista = raiz.dataset.vista || "usuario";
    var activos = parseInt(raiz.dataset.activos, 10) || 0;
    var vencidos = parseInt(raiz.dataset.vencidos, 10) || 0;
    var sinAsignar = parseInt(raiz.dataset.sinAsignar, 10) || 0;
    var porConfirmar = parseInt(raiz.dataset.porConfirmar, 10) || 0;
    var coma = nombre ? ", " + nombre : "";

    var estados = {
        principal: {
            archivo: "Mascota.png",
            frases: ["Aquí estoy para ayudarte ☕", "Soporte técnico a tus órdenes", "Café listo, ¿empezamos?", "Todo bajo control por aquí"]
        },
        hola: {
            archivo: "hola.png",
            frases: ["¡Hola" + coma + "!", "¡Qué gusto verte!", "¡Hola, hola! 👋", "¡Bienvenido de vuelta!"]
        },
        alegre: {
            archivo: "alegre.png",
            frases: ["¡Qué buen día para resolver tickets!", "¡Vamos con todo!", "¡Yuju!"]
        },
        alegre2: {
            archivo: "alegre2.png",
            frases: ["¡Eso es!", "¡Lo logramos!", "¡Arriba ese ánimo!"]
        },
        alegre3: {
            archivo: "alegre3.png",
            frases: ["¡Gracias por visitarme!", "¡Me encanta ayudar!", "¡Buena vibra!"]
        },
        asomando: {
            archivo: "azomando cabeza.png",
            frases: ["¿Me buscabas?", "Cucú… 👀", "Te estaba espiando, perdón"]
        },
        confiado: {
            archivo: "confiado.png",
            frases: ["Yo me encargo.", "Tranquilo, tiene solución.", "Eso lo arreglamos en un momento"]
        },
        confundido: {
            archivo: "confundido.png",
            frases: ["Uy… todo me da vueltas", "¿Dónde dejé mi café?", "Me mareé tantito"]
        },
        cool: {
            archivo: "cool.png",
            frases: ["Soporte nivel experto 😎", "Con estilo se resuelve mejor", "Sin sudar"]
        },
        curioso: {
            archivo: "curioso.png",
            frases: ["¿Y eso qué es?", "Mmm… déjame ver", "Qué interesante…"]
        },
        dormir: {
            archivo: "dormir.png",
            frases: ["Zzz…", "Zzz… cinco minutitos más…"]
        },
        enojado: {
            archivo: "enojado.png",
            frases: ["¡Ya, ya! Tengo trabajo", "¡Oye! Me van a descomponer", "¡Basta de clics! 💢"]
        },
        pregunta: {
            archivo: "pregunta.png",
            frases: ["¿En qué te ayudo?", "¿Algo no funciona?", "¿Tienes alguna duda?"]
        },
        sorprendido: {
            archivo: "sorprendido.png",
            frases: ["¡Oh!", "¡No lo vi venir!", "¿Qué fue eso?"]
        },
        timido: {
            archivo: "timido.png",
            frases: ["Ay, me da pena…", "Hola… ¿tú otra vez?", "No me mires tanto"]
        },
        triste: {
            archivo: "triste.png",
            frases: ["Se me acabó el café…", "Nadie me saluda hoy…", "Snif…"]
        }
    };

    var ciclo = ["alegre", "curioso", "confiado", "cool", "alegre2", "pregunta", "alegre3", "asomando", "timido", "triste", "hola"];
    var reacciones = ["hola", "alegre", "timido", "curioso", "cool", "alegre2", "alegre3", "asomando", "sorprendido"];

    function plural(n, singular, plural_) {
        return n + " " + (n === 1 ? singular : plural_);
    }

    var contextuales = [];
    if (vista === "usuario") {
        if (porConfirmar) {
            contextuales.push({ estado: "curioso", frase: plural(porConfirmar, "ticket espera", "tickets esperan") + " tu confirmación" });
        } else if (activos) {
            contextuales.push({ estado: "confiado", frase: "Seguimos con " + plural(activos, "ticket", "tickets") + " tuyo" + (activos === 1 ? "" : "s") });
        } else {
            contextuales.push({ estado: "pregunta", frase: "¿Algo no funciona? Cuéntanos y te ayudamos" });
        }
    } else {
        if (vencidos) {
            contextuales.push({ estado: "sorprendido", frase: "¡Ojo! " + plural(vencidos, "ticket", "tickets") + " con SLA vencido" });
        }
        if (sinAsignar) {
            contextuales.push({ estado: "pregunta", frase: plural(sinAsignar, "ticket", "tickets") + " sin asignar, ¿los tomamos?" });
        }
        if (!vencidos && !sinAsignar) {
            contextuales.push({ estado: "cool", frase: "Todo en orden. ¡Buen trabajo!" });
        }
    }

    var activa = 0;
    var ahora = "principal";
    var turno = 0;
    var dormida = false;
    var sobre = false;
    var saludada = false;
    var clics = 0;
    var ultimoClic = 0;
    var ultimaActividad = 0;
    var bloqueoHasta = 0;
    var ultimasFrases = {};
    var temporizadorGlobo = null;
    var temporizadorRegreso = null;
    var temporizadorSueno = null;

    function azar(lista) {
        return lista[Math.floor(Math.random() * lista.length)];
    }

    function azarDistinto(lista, excluido) {
        return azar(lista.filter(function (x) {
            return x !== excluido;
        }));
    }

    function frase(estado) {
        var lista = estados[estado].frases;
        var elegida = lista.length > 1 ? azarDistinto(lista, ultimasFrases[estado]) : lista[0];
        ultimasFrases[estado] = elegida;
        return elegida;
    }

    function url(estado) {
        return base + encodeURIComponent(estados[estado].archivo);
    }

    function mostrar(estado) {
        if (estado === ahora) {
            return;
        }
        var mio = ++turno;
        var hecho = false;
        var saliente = capas[activa];
        var entrante = capas[1 - activa];

        function listo() {
            if (hecho || mio !== turno) {
                return;
            }
            hecho = true;
            entrante.classList.remove("pop");
            void entrante.offsetWidth;
            entrante.classList.add("pop", "activa");
            saliente.classList.remove("activa");
            activa = 1 - activa;
            ahora = estado;
        }

        entrante.onload = listo;
        entrante.src = url(estado);
        if (entrante.complete && entrante.naturalWidth) {
            listo();
        }
    }

    function decir(mensaje, ms) {
        textoGlobo.textContent = mensaje;
        globo.classList.remove("visible");
        void globo.offsetWidth;
        globo.classList.add("visible");
        clearTimeout(temporizadorGlobo);
        temporizadorGlobo = setTimeout(callar, ms || 4000);
    }

    function callar() {
        clearTimeout(temporizadorGlobo);
        globo.classList.remove("visible");
    }

    function ir(estado, mensaje, ms) {
        mostrar(estado);
        if (mensaje) {
            decir(mensaje, ms);
        } else {
            callar();
        }
    }

    function programarRegreso(ms) {
        clearTimeout(temporizadorRegreso);
        temporizadorRegreso = setTimeout(function () {
            if (sobre || dormida) {
                return;
            }
            callar();
            mostrar("principal");
        }, ms);
    }

    function dormir() {
        dormida = true;
        ir("dormir", frase("dormir"), 4000);
    }

    function actividad() {
        var t = Date.now();
        if (!dormida && t - ultimaActividad < 1000) {
            return;
        }
        ultimaActividad = t;
        clearTimeout(temporizadorSueno);
        if (dormida) {
            dormida = false;
            bloqueoHasta = t + 3000;
            ir("sorprendido", "¡Ah! Ya desperté…", 2800);
            if (!sobre) {
                programarRegreso(3000);
            }
        }
        temporizadorSueno = setTimeout(dormir, 60000);
    }

    function paso() {
        if (!document.hidden && !sobre && !dormida && Date.now() >= bloqueoHasta) {
            var r = Math.random();
            if (contextuales.length && r < 0.3) {
                var c = azar(contextuales);
                ir(c.estado, c.frase, 4500);
            } else if (ahora !== "principal" && r < 0.6) {
                ir("principal", Math.random() < 0.4 ? frase("principal") : null);
            } else {
                var e = azarDistinto(ciclo, ahora);
                ir(e, Math.random() < 0.65 ? frase(e) : null);
            }
        }
        setTimeout(paso, 5000 + Math.random() * 5000);
    }

    function precargar() {
        var nombres = Object.keys(estados);
        var i = 0;
        (function siguiente() {
            if (i >= nombres.length) {
                return;
            }
            var im = new Image();
            im.onload = im.onerror = function () {
                setTimeout(siguiente, 300);
            };
            im.src = url(nombres[i++]);
        })();
    }

    escena.addEventListener("pointerenter", function (ev) {
        if (ev.pointerType !== "mouse") {
            return;
        }
        actividad();
        sobre = true;
        clearTimeout(temporizadorRegreso);
        bloqueoHasta = Date.now() + 4000;
        var estado = saludada ? azarDistinto(reacciones, ahora) : "hola";
        saludada = true;
        ir(estado, frase(estado), 3200);
    });

    escena.addEventListener("pointerleave", function (ev) {
        if (ev.pointerType !== "mouse") {
            return;
        }
        sobre = false;
        programarRegreso(2500);
    });

    escena.addEventListener("click", function () {
        actividad();
        var t = Date.now();
        clics = t - ultimoClic < 1200 ? clics + 1 : 1;
        ultimoClic = t;
        bloqueoHasta = t + 4000;
        var estado;
        if (clics >= 6) {
            estado = "enojado";
            clics = 0;
        } else if (clics >= 4) {
            estado = "confundido";
        } else {
            estado = azarDistinto(reacciones, ahora);
        }
        ir(estado, frase(estado), 3200);
        if (!sobre) {
            programarRegreso(3500);
        }
    });

    ["pointermove", "keydown", "touchstart", "scroll"].forEach(function (nombreEvento) {
        document.addEventListener(nombreEvento, actividad, { passive: true });
    });

    window.addEventListener("load", function () {
        setTimeout(precargar, 1200);
    });

    temporizadorSueno = setTimeout(dormir, 60000);
    setTimeout(function () {
        decir("¡Hola" + coma + "!", 3800);
    }, 800);
    setTimeout(paso, 8000);
})();