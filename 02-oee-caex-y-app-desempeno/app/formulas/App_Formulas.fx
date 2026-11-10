// App.Formulas — fórmulas con nombre (se pegan en la propiedad Formulas del objeto App).
// Paleta Minera Demo
colPrimario = RGBA(27, 42, 65, 1);
colPrimarioClaro = RGBA(223, 229, 238, 1);
colFondo = RGBA(245, 246, 248, 1);
colTexto = RGBA(33, 37, 41, 1);
colVerde = RGBA(46, 125, 50, 1);
colAmbar = RGBA(237, 108, 2, 1);
colRojo = RGBA(198, 40, 40, 1);
// Acentos de la paleta Minera Demo (azul cielo; naranjo de aviso)
colAzul = RGBA(79, 157, 222, 1);
colNaranja = RGBA(242, 140, 40, 1);

// Semáforo de KPIs en 3 niveles: verde si Real ≥ Plan, naranjo si Real ≥ 95 % del plan, rojo bajo eso.
nUmbralAmbar = 95 / 100;

// Reunión semanal de supervisores, los lunes. Día de la semana con StartOfWeek.Monday: 1 = lunes … 7 = domingo.
nDiaReunion = 1;
txtDiaReunion = "lunes";
// Agenda: 1 Seguridad, 2 solo revisión de compromisos de la semana pasada, 3 Indicadores y 4 Cierre con los compromisos nuevos.
// El visor numera por N y «Siguiente» suma 1. Minutos por bloque: 5 + 10 + 20 + 5 = 40. nMinutosMeta sale de la suma, así que
// el título de la Agenda, los cronómetros, Inicio y la minuta se ajustan solos.
tblBloques = Table(
    {N: 1, Bloque: "Seguridad", Min: 5},
    {N: 2, Bloque: "Compromisos", Min: 10},
    {N: 3, Bloque: "Indicadores", Min: 20},
    {N: 4, Bloque: "Cierre", Min: 5}
);
nMinutosMeta = Sum(tblBloques, Min);

tblEstadosCompromiso = ["En progreso", "Cumplido", "Atrasado"];
tblCategoriasIdea = ["Seguridad", "Producción", "Innovación", "Sustentabilidad", "Mejora continua"];

// Reunión semanal (nDiaReunion). La preparación que se hace en el modo editor se guarda por fecha de reunión.
// fecReunion = hoy si es el día de la reunión y todavía no se cerró; si no, el próximo día de reunión.
fecReunion =
    If(
        Weekday(Today(), StartOfWeek.Monday) = nDiaReunion &&
        IsEmpty(colSesionesHoy) &&
        IsBlank(LookUp(colOutSesiones, Fecha = Text(Today(), "yyyy-mm-dd"))),
        Today(),
        DateAdd(Today(), Mod(nDiaReunion - Weekday(Today(), StartOfWeek.Monday) + 6, 7) + 1, TimeUnit.Days)
    );
claveReunion = Text(fecReunion, "yyyy-mm-dd");

// Preparación guardada: la escribe el editor y la lee el visor (Excel RD_Preparacion, nadie la edita a mano).
// Es un JSON con el tema de seguridad (seg), el estado de cada compromiso (est), los destacados (des), los avisos con nivel (avi)
// y los indicadores de seguridad (ind); seg queda como resumen.
fxPrepVacio = "{""seg"":"""",""est"":[],""des"":[]}";
fxPrepFila = LookUp(colPrepFila, Clave = claveReunion);
fxPrep = ParseJSON(Coalesce(fxPrepFila.Json, fxPrepVacio));
fxSeg = Coalesce(Text(fxPrep.seg), "");

// Seguridad: recuadros con indicadores arriba y avisos con nivel abajo.
// Avisos (avi): nivel Crítico, Precaución o Recordar. Rango ordena del más grave al más leve.
// Las preparaciones que solo traen el texto (seg) leen cada línea como un aviso sin nivel ("Aviso").
fxAvisos =
    If(
        IsBlank(fxPrep.avi),
        With(
            {l: Filter(Split(Substitute(fxSeg, Char(13), ""), Char(10)), !IsBlank(Trim(Value)))},
            ForAll(
                Sequence(CountRows(l)) As i,
                {Nivel: "Aviso", Texto: Trim(Index(l, i.Value).Value), Orden: i.Value, IdLocal: "seg" & i.Value, Rango: 4}
            )
        ),
        ForAll(
            Table(fxPrep.avi) As a,
            With(
                {n: Text(a.Value.n)},
                {Nivel: n, Texto: Text(a.Value.x), Orden: Value(a.Value.o), IdLocal: Text(a.Value.id), Rango: Switch(n, "Crítico", 1, "Precaución", 2, "Recordar", 3, 4)}
            )
        )
    );
// Indicadores de seguridad (ind): no hay un modelo de donde sacarlos, se escriben a mano en el editor. Vacíos = Blank.
// Rep / RepMeta (claves rep / repm) se muestran en la app como «Hipo Hazard».
fxIndSeg = {
    Inc: Value(fxPrep.ind.inc),
    IncAnt: Value(fxPrep.ind.inca),
    Rep: Value(fxPrep.ind.rep),
    RepMeta: Value(fxPrep.ind.repm),
    InsReal: Value(fxPrep.ind.ire),
    InsPlan: Value(fxPrep.ind.ipl)
};

// Compromisos abiertos con el estado preparado. EstadoAnterior es el último estado registrado.
// Un estado "Bloqueado" de registros antiguos se lee como "Atrasado".
fxRevision =
    ForAll(
        colCompromisos As c,
        With(
            {
                e: LookUp(Table(fxPrep.est), Value(ThisRecord.Value.id) = c.ID),
                est0: If(c.Estado = "Bloqueado", "Atrasado", c.Estado)
            },
            {
                ID: c.ID,
                Titulo: c.Titulo,
                ResponsableNombre: c.ResponsableNombre,
                FechaLimite: c.FechaLimite,
                FechaCreacion: c.FechaCreacion,
                EstadoAnterior: est0,
                EstadoNuevo: Coalesce(Text(e.Value.estado), est0),
                Revisado: Coalesce(Boolean(e.Value.rev), false),
                Comentario: Coalesce(Text(e.Value.com), ""),
                Url: Coalesce(Text(e.Value.url), "")
            }
        )
    );

// Páginas del visor: la Agenda (página 0, sin tiempo propio) y los bloques con tiempo de tblBloques (1 a 4).
tblPaginasVisor =
    ForAll(
        Sequence(CountRows(tblBloques) + 1, 0) As s,
        {
            N: s.Value,
            Bloque: If(s.Value = 0, "Agenda", LookUp(tblBloques, N = s.Value).Bloque),
            Min: If(s.Value = 0, 0, LookUp(tblBloques, N = s.Value).Min)
        }
    );

// Segundos usados en cada página de la reunión (las ya terminadas más la que está en curso).
// Es solo un indicador: pasarse del tiempo pone el cronómetro en rojo, pero nunca cierra la reunión.
fxTiemposBloques =
    ForAll(
        tblPaginasVisor As b,
        {
            N: b.N,
            Min: b.Min,
            Seg: If(varBloque = b.N, DateDiff(varBloqueInicio, varAhora, TimeUnit.Seconds), 0) + Sum(Filter(colTiempos, Bloque = b.N), Seg)
        }
    );

// Destacados preparados: highlights, lowlights y temas a discutir. La app ya no los muestra ni los sube; la fórmula se
// conserva para no perder lo que traiga una preparación anterior y para que colOutDestacados conserve su forma en Inicio.
fxDest =
    ForAll(
        Table(fxPrep.des) As d,
        {
            Tipo: Text(d.Value.t),
            Texto: Text(d.Value.x),
            Orden: Value(d.Value.o),
            IdLocal: Text(d.Value.id)
        }
    );

// Registros guardados en el equipo que faltan por subir (Excel de RD/Datos).
nPendientes =
    CountRows(colOutSesiones) + CountRows(colOutRevisiones) + CountRows(colOutCompromisos) +
    CountRows(colOutEvidencias) + CountRows(colOutDestacados) + CountRows(colOutPrep) +
    CountRows(colOutAsistencia) + CountRows(colOutMinuta);
