Convenciones y lectura rápida



Estilos (style\_key):



flamenco\_rumba



urban\_trap



rock



latin\_pop



edm



ballad\_ambient



acoustic



Buses (bus\_key):



drums



bass



guitars



keys\_synth



lead\_vocal



backing\_vocals



fx



misc (material no clasificado / “other” / “auto”)



Reverb models (Pedalboard.Reverb arquetipos):



room → salas pequeñas / rooms cortos

Aproximadamente 0.6–0.9 s de cola.



spring → tipo muelles, mid-rangey

Aprox. 0.8–1.0 s.



plate → plate vocal/guitarra clásico, bright controlado

Aprox. 1.2–1.8 s.



hall → hall grande pero filtrado

Aprox. 2.0–2.8 s.



Send level (dB) y porcentaje aproximado de “envío FX”:



Recordatorio: esto es el factor con el que se escala el bus FX (100 % wet) antes de sumarlo al dry.



dB send	% aprox. (lineal)

-12 dB	~25 %

-13 dB	~22 %

-14 dB	~20 %

-15 dB	~18 %

-16 dB	~16 %

-17 dB	~14 %

-18 dB	~13 %

-20 dB	~10 %

-22 dB	~8 %

-24 dB	~6 %

-26 dB	~5 %

-40 dB	~1 %

-45 dB	~0.6 %

-50 dB	~0.3 %

-55 dB	~0.2 %



Filtros en el bus FX (antes de la reverb/delay):



hp\_hz alto = limpia graves de la cola → mezcla más “profesional”, menos bola.



lp\_hz más bajo = cola menos brillante → reverb más “atrás” y menos chillona.



Estilo: flamenco\_rumba



Idea general

Sonido natural, cercano y dinámico. Guitarras y voces con plate corto y predelays generosos para preservar ataque y articulación. Muy poco FX en graves; FX más largos solo en fx y misc.



Bus	Reverb / Decay aprox.	Predelay	Send (dB / % aprox.)	Extras (delay / mod)	Filtros FX (HP / LP)	Intención sonora

drums	room (~0.7 s), estéreo tight	10 ms	-20 dB (~10 %)	Sin delay creativo; sin mod	HP ≈ 320 Hz / LP ≈ 11 kHz	Un pequeño room que da “glue” al kit/percusiones sin llenar bajos; percusión flamenca sigue sonando natural y cercana.

bass	prácticamente seco (no override de reverb)	5 ms	-40 dB (~1 %)	Sin delay, sin mod	HP ≈ 80 Hz / LP ≈ 6.5 kHz	Bajo muy seco; apenas una sombra de room. Evita bola de graves y mantiene la base muy definida, típico en mezclas acústicas/flamencas.

guitars	plate corto (~1.4 s)	28 ms	-18 dB (~13 %)	Delay 210 ms, feedback 0.16; chorus suave (rate 0.8 Hz, depth 0.10)	HP ≈ 220 Hz / LP ≈ 11.5 kHz	Guitarras flamencas/rumba con plate clásico, predelay para no tapar el ataque y un eco corto que abre estéreo sin emborronar.

keys\_synth	hall compacto (~2.0 s)	24 ms	-20 dB (~10 %)	Delay 280 ms, feedback 0.18	HP ≈ 240 Hz / LP ≈ 15 kHz	Pianos/keys/pads que aportan atmósfera pero siguen siendo secundarios; hall contenido y filtrado para no robar protagonismo a guitarra y voz.

lead\_vocal	plate (~1.6–1.8 s)	90 ms	-16 dB (~16 %)	Slapback 150 ms, feedback 0.22; chorus muy ligero	HP ≈ 170 Hz / LP ≈ 12 kHz	Voz principal flamenca adelantada, con predelay largo para claridad en consonantes, plate vocal con cola elegante y un slap corto que da densidad.

backing\_vocals	hall moderado (~2.2 s)	60 ms	-14 dB (~20 %)	Delay 260 ms, feedback 0.26; chorus suave	HP ≈ 190 Hz / LP ≈ 13.5 kHz	Coros algo más húmedos y atrás, creando un colchón alrededor de la lead sin competir en presencia ni en inteligibilidad.

fx	hall algo más largo (~2.5 s)	40 ms	-12 dB (~25 %)	Delay 380 ms, feedback 0.32; phaser suave	HP ≈ 260 Hz / LP ≈ 16.5 kHz	FX ambientales (palmas procesadas, reversos, golpes) con un espacio más grande y mod suave que aporta sensación “escénica” sin ensuciar el mid-range.

misc	room neutro corto	18 ms	-20 dB (~10 %)	Sin delay/mod	HP ≈ 230 Hz / LP ≈ 13 kHz	Cualquier fuente no clasificada recibe un room discreto que da coherencia espacial sin introducir colas largas ni exceso de brillo.

Estilo: urban\_trap



Idea general

Kick y sub muy secos. Vox con plate/hall brillante, predelay largo y delays claros. FX grandes y creativos pero muy filtrados en graves.



Bus	Reverb / Decay aprox.	Predelay	Send (dB / % aprox.)	Extras (delay / mod)	Filtros FX (HP / LP)	Intención sonora

drums	room pequeño (~0.6–0.7 s)	6 ms	-22 dB (~8 %)	Sin delay/mod	HP ≈ 350 Hz / LP ≈ 10 kHz	Room muy discreto que une elementos de batería pero mantiene el golpe seco y controlado típico de trap.

bass	prácticamente seco	5 ms	-50 dB (~0.3 %)	Sin delay/mod	HP ≈ 70 Hz / LP ≈ 6 kHz	Sub-bass casi sin espacio artificial; el low end queda hiper definido y sin colas que se coman el headroom.

guitars	plate (~1.4–1.6 s)	24 ms	-20 dB (~10 %)	Delay 260 ms, feedback 0.20; chorus ligero	HP ≈ 230 Hz / LP ≈ 11.5 kHz	Guitarras y samples se integran en el beat sin saturar el campo estéreo; cola plate controlada y eco musical.

keys\_synth	hall moderado (~2.0 s)	30 ms	-18 dB (~13 %)	Delay 320 ms, feedback 0.26; chorus suave	HP ≈ 260 Hz / LP ≈ 16 kHz	Pads y synths envuelven la base, pero filtrados para dejar hueco a voz y 808; típico “cloudy pad” urbano.

lead\_vocal	plate brillante (~1.6–1.8 s)	100 ms	-14 dB (~20 %)	Delay 260 ms (eco 1/8–1/4), feedback 0.28; chorus ligero	HP ≈ 180 Hz / LP ≈ 12.5 kHz	Lead muy al frente, con predelay largo y plate brillante; el delay aporta groove sin embarrar, como en voces main de trap/hip-hop actual.

backing\_vocals	hall (~2.1–2.3 s)	70 ms	-12 dB (~25 %)	Delay 320 ms, feedback 0.30	HP ≈ 200 Hz / LP ≈ 13.5 kHz	Dobles y ad-libs más atrás y húmedos; relleno estéreo y profundidad, separando claramente lead y coros.

fx	hall largo (~2.5–2.7 s)	45 ms	-10 dB (~32 %)	Delay 420 ms, feedback 0.38; phaser suave	HP ≈ 280 Hz / LP ≈ 18 kHz	Risers, impacts, chops vocales con colas largas y modulación que crean la sensación “cinematográfica” típica del género sin invadir el rango vocal principal.

misc	room neutro	16 ms	-22 dB (~8 %)	Sin delay/mod	HP ≈ 250 Hz / LP ≈ 13 kHz	Material residual tratado con room discreto para cohesión, manteniendo la claridad general del beat.

Estilo: rock



Idea general

Baterías con room reconocible, guitarras con plate/delay, voces con plate vocal clásico, coros algo más largos. Todo bastante filtrado por arriba y por abajo para no saturar la mezcla.



Bus	Reverb / Decay aprox.	Predelay	Send (dB / % aprox.)	Extras (delay / mod)	Filtros FX (HP / LP)	Intención sonora

drums	room (~0.7 s)	14 ms	-18 dB (~13 %)	Sin delay/mod	HP ≈ 280 Hz / LP ≈ 11 kHz	Room que da carácter a la batería (tipo overhead/room mics) sin volverse demasiado ambient.

bass	prácticamente seco	5 ms	-45 dB (~0.6 %)	Sin delay/mod	HP ≈ 80 Hz / LP ≈ 6.5 kHz	Bajo eléctrico con cuerpo pero casi sin cola artificial, dejando espacio al bombo y a la caja.

guitars	plate (~1.4–1.6 s)	26 ms	-18 dB (~13 %)	Delay 280 ms, fb 0.20; chorus suave	HP ≈ 220 Hz / LP ≈ 11.5 kHz	Guitarras con plate rock clásico + eco que da profundidad y anchura sin tapar medios vocales.

keys\_synth	hall moderado (~2.0 s)	24 ms	-18 dB (~13 %)	Delay 320 ms, fb 0.22	HP ≈ 240 Hz / LP ≈ 15 kHz	Teclados de acompañamiento con hall controlado, relleno pero no protagónico.

lead\_vocal	plate vocal (~1.6–1.8 s)	70 ms	-16 dB (~16 %)	Delay 170 ms, fb 0.22; chorus ligero	HP ≈ 170 Hz / LP ≈ 12 kHz	Sonido de voz rock típico: en primer plano, plate con cola presente pero controlada y un eco muy corto que engorda sin emborronar la dicción.

backing\_vocals	hall (~2.1–2.3 s)	50 ms	-14 dB (~20 %)	Delay 260 ms, fb 0.26	HP ≈ 190 Hz / LP ≈ 13.5 kHz	Coros más abiertos y atrás, generando “coro de estadio” suave que se separa bien de la lead.

fx	hall más largo (~2.4–2.6 s)	30 ms	-12 dB (~25 %)	Delay 360 ms, fb 0.35; phaser suave	HP ≈ 260 Hz / LP ≈ 16.5 kHz	FX de transición, reverbs de caja creativas, etc., con colas más presentes pero muy filtradas.

misc	room neutro	15–18 ms	-20 dB (~10 %)	Sin delay/mod	HP ≈ 230–250 Hz / LP ≈ 13 kHz	Pegamento espacial para cualquier elemento residual sin crear colas extra innecesarias.

Estilo: latin\_pop



Idea general

Similar al urban, pero todo un punto más suave y musical. Voces con plate/hall claro, drums algo más “elegantes”, FX presentes pero no tan extremos.



Bus	Reverb / Decay aprox.	Predelay	Send (dB / % aprox.)	Extras (delay / mod)	Filtros FX (HP / LP)	Intención sonora

drums	room (~0.7 s)	10 ms	-20 dB (~10 %)	Sin delay/mod	HP ≈ 320 Hz / LP ≈ 10.5 kHz	Room ligero que suaviza transitorios y da cohesión en grooves bailables sin perder pegada.

bass	prácticamente seco	5 ms	-45 dB (~0.6 %)	Sin delay/mod	HP ≈ 80 Hz / LP ≈ 6.5 kHz	Bajo centrado y definido; low end de reggaeton/latin pop sin colas largas.

guitars	plate (~1.4–1.6 s)	24 ms	-18 dB (~13 %)	Delay 240 ms, fb 0.20; chorus suave	HP ≈ 220 Hz / LP ≈ 11.5 kHz	Guitarras (acústicas/electricas) con plate musical y eco medio que las asienta en el groove.

keys\_synth	hall moderado (~2.0 s)	28 ms	-18 dB (~13 %)	Delay 300 ms, fb 0.24	HP ≈ 240 Hz / LP ≈ 15 kHz	Teclados/pads que aportan atmósfera tropical/pop sin tapar las voces ni el beat.

lead\_vocal	plate vocal (~1.6–1.8 s)	90 ms	-15 dB (~18 %)	Delay 230 ms, fb 0.26; chorus ligero	HP ≈ 180 Hz / LP ≈ 12.5 kHz	Lead vocal muy presente y moderna, con plate pop y eco que refuerza el ritmo sin estropear la claridad.

backing\_vocals	hall (~2.1–2.3 s)	60 ms	-13 dB (~22 %)	Delay 280 ms, fb 0.28	HP ≈ 200 Hz / LP ≈ 13.5 kHz	Coros envolventes y algo más húmedos, rodeando la lead para estribillos grandes.

fx	hall largo (~2.4–2.6 s)	40 ms	-11 dB (~28 %)	Delay 380 ms, fb 0.34; phaser suave	HP ≈ 270 Hz / LP ≈ 17.5 kHz	FX con colas amplias y movimiento, ideales para transiciones de estribillo a estrofa o drops suaves.

misc	room neutro	16 ms	-22 dB (~8 %)	Sin delay/mod	HP ≈ 250 Hz / LP ≈ 13 kHz	Cohesión espacial para elementos varios sin exagerar la sensación de sala.

Estilo: edm



Idea general

Drums y bass muy secos y contundentes. Keys y FX con halls grandes y creativos, colas largas filtradas en graves y bastante brillo controlado arriba.



Bus	Reverb / Decay aprox.	Predelay	Send (dB / % aprox.)	Extras (delay / mod)	Filtros FX (HP / LP)	Intención sonora

drums	room corto (~0.6–0.7 s)	6 ms	-22 dB (~8 %)	Sin delay/mod	HP ≈ 380 Hz / LP ≈ 10 kHz	Room mínimo para cohesión; el bombo/percusiones siguen ultra secos y punchy, como en club.

bass	seco	5 ms	-55 dB (~0.2 %)	Sin delay/mod	HP ≈ 70 Hz / LP ≈ 5.5 kHz	Sub-bass/mono bass prácticamente sin FX; todo el espacio se delega a pads y FX para preservar pegada en el low end.

guitars	plate (~1.4–1.6 s)	22 ms	-20 dB (~10 %)	Delay 260 ms, fb 0.24; chorus ligero	HP ≈ 230 Hz / LP ≈ 11.5 kHz	Guitarras (si las hay) integradas como capa adicional, sin competir con synths ni leads principales.

keys\_synth	hall grande (~2.4–2.8 s)	35 ms	-14 dB (~25 %)	Delay 350 ms, fb 0.32; chorus profundo (depth 0.22 aprox.)	HP ≈ 260 Hz / LP ≈ 17 kHz	Pads y supersaws super amplios y envolventes, colas largas y modulación suave típicas de EDM mainstage.

lead\_vocal	hall vocal moderno (~2.0–2.3 s)	90 ms	-15 dB (~18 %)	Delay 280 ms, fb 0.30; chorus ligero	HP ≈ 190 Hz / LP ≈ 13 kHz	Voz principal moderna y limpia que flota encima del muro de synths, con delays claros y hall controlado.

backing\_vocals	hall (~2.3–2.5 s)	60 ms	-13 dB (~22 %)	Delay 320 ms, fb 0.32	HP ≈ 210 Hz / LP ≈ 14 kHz	Coros/dobles en un plano más ambient, reforzando estribillos sin competir con el lead ni con los synths.

fx	hall muy largo (~2.6–3.0 s)	40 ms	-10 dB (~32 %)	Delay 420 ms, fb 0.40; phaser marcado	HP ≈ 300 Hz / LP ≈ 19 kHz	Risers, impacts, sweeps con colas exageradas y movimiento estéreo que construyen energía de club.

misc	room neutro	16–18 ms	-20 a -22 dB (~8–10 %)	Sin delay/mod	HP ≈ 240–260 Hz / LP ≈ 13–14 kHz	Cohesión de elementos extra sin añadir más “wash” a una mezcla ya muy espacial en pads/FX.

Estilo: ballad\_ambient



Idea general

Halls largos pero muy filtrados; mucho espacio, pero controlado en graves. Voces con colas bonitas y predelays generosos; guitars/keys envuelven.



Bus	Reverb / Decay aprox.	Predelay	Send (dB / % aprox.)	Extras (delay / mod)	Filtros FX (HP / LP)	Intención sonora

drums	room suave (~0.7 s)	12 ms	-20 dB (~10 %)	Sin delay/mod	HP ≈ 320 Hz / LP ≈ 10 kHz	Batería/percusiones con algo de aire, pero sin convertirse en verb wash; sigue habiendo definición.

bass	casi seco	5 ms	-45 dB (~0.6 %)	Sin delay/mod	HP ≈ 80 Hz / LP ≈ 6.5 kHz	Bajo definido para anclar la mezcla; el ambiente viene de guitars/keys/vox.

guitars	hall (~2.3–2.5 s)	30 ms	-18 dB (~13 %)	Delay 280 ms, fb 0.26; chorus suave	HP ≈ 240 Hz / LP ≈ 12 kHz	Guitarras atmosféricas y anchas, típicas de baladas y ambient, que rellenan sin tapar la voz.

keys\_synth	hall grande (~2.6–2.8 s)	35 ms	-16 dB (~16 %)	Delay 360 ms, fb 0.32; chorus más profundo	HP ≈ 260 Hz / LP ≈ 16 kHz	Pads/keys casi “cine”, con colas largas y modulación lenta que generan espacio envolvente.

lead\_vocal	hall vocal (~2.2–2.5 s)	95 ms	-16 dB (~16 %)	Delay 260 ms, fb 0.28; chorus ligero	HP ≈ 180 Hz / LP ≈ 12.5 kHz	Lead vocal emotiva y flotante; predelay largo asegura claridad en palabras aunque la cola sea grande.

backing\_vocals	hall largo (~2.6–2.8 s)	70 ms	-14 dB (~20 %)	Delay 320 ms, fb 0.32; chorus algo más marcado	HP ≈ 200 Hz / LP ≈ 13.5 kHz	Coros muy atmosféricos, casi pads vocales, envolviendo la lead en ambientes tipo “dream pop / ambient”.

fx	hall muy largo (~2.8–3.0 s)	45 ms	-12 dB (~25 %)	Delay 420 ms, fb 0.38; phaser suave	HP ≈ 280 Hz / LP ≈ 18 kHz	FX con colas etéreas que se integran con pads y coros, ampliando aún más la sensación de espacio.

misc	room neutro	18 ms	-20 dB (~10 %)	Sin delay/mod	HP ≈ 230–250 Hz / LP ≈ 13 kHz	Cohesión espacial suave para fuentes secundarias sin sumar demasiada cola extra.

Estilo: acoustic



Idea general

Muy orientado a producciones íntimas: rooms cortos, plates suaves para voz, casi todo relativamente seco. Mucho HP en el FX para que el grave se perciba directo y no “barroso”.



Bus	Reverb / Decay aprox.	Predelay	Send (dB / % aprox.)	Extras (delay / mod)	Filtros FX (HP / LP)	Intención sonora

drums	room pequeño (~0.6–0.7 s)	8 ms	-22 dB (~8 %)	Sin delay/mod	HP ≈ 320 Hz / LP ≈ 10 kHz	Si hay batería/percusiones, se colocan ligeramente en sala, pero siguen sonando bastante “en la cara”.

bass	casi seco	5 ms	-50 dB (~0.3 %)	Sin delay/mod	HP ≈ 90 Hz / LP ≈ 6.5 kHz	Bajo acústico o eléctrico muy presente y limpio, sin “cola artificial” que estropee la naturalidad.

guitars	room (~0.7–0.9 s)	18 ms	-20 dB (~10 %)	Delay 220 ms, fb 0.16	HP ≈ 220 Hz / LP ≈ 11.5 kHz	Guitarras acústicas con un poco de room y eco corto para dar profundidad, pero conservando sensación de “micro cercano”.

keys\_synth	room (~0.8 s)	20 ms	-20 dB (~10 %)	Delay 260 ms, fb 0.18	HP ≈ 230 Hz / LP ≈ 13.5 kHz	Pianos y keys ligeros, con espacio muy moderado, más en la línea de grabación de estudio pequeña que de hall grande.

lead\_vocal	plate suave (~1.4–1.6 s)	70 ms	-17 dB (~14 %)	Delay 150 ms, fb 0.22; chorus muy ligero	HP ≈ 180 Hz / LP ≈ 12 kHz	Voz íntima, en primer plano, con plate controlado y eco corto; sensación de “cantante en la misma habitación”.

backing\_vocals	hall controlado (~2.0–2.2 s)	55 ms	-15 dB (~18 %)	Delay 260 ms, fb 0.24	HP ≈ 200 Hz / LP ≈ 13 kHz	Coros un poco más atrás para acompañar sin quitar protagonismo al mensaje de la lead.

fx	hall moderado (~2.2–2.4 s)	35 ms	-13 dB (~22 %)	Delay 360 ms, fb 0.30	HP ≈ 260 Hz / LP ≈ 17 kHz	FX ambiente discreto (ruidos de sala, foley suave, etc.) que amplían la escena sin romper la estética acústica.

misc	room neutro	16 ms	-22 dB (~8 %)	Sin delay/mod	HP ≈ 230 Hz / LP ≈ 13 kHz	Pequeño room para otros elementos, manteniendo siempre la sensación de “grupo tocando en una sala real”.

