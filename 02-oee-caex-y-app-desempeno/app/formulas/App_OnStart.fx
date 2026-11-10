// App.OnStart — recupera preferencias y la bandeja de salida guardada en el equipo.
// Reunión única de todos los supervisores: sin selector de grupo.
Set(gblGrupo, "Supervisores");
Set(varReunionEnCurso, false);
// Modo editor (preparación de la reunión): sin cambios pendientes al abrir la app.
Set(varPrepSucia, false);
Set(varPrepGuardando, false);
Set(varPrepNube, false);
Set(varPrepErr, "");
Set(varPrepFecha, "");
Set(varSeg, "");
Set(varEvidId, 0);
Set(varBloqueEd, 1);
LoadData(colOutSesiones, "rd_out_ses", true);
LoadData(colOutRevisiones, "rd_out_rev", true);
LoadData(colOutCompromisos, "rd_out_comp", true);
LoadData(colOutEvidencias, "rd_out_evid", true);
LoadData(colOutDestacados, "rd_out_dest", true);
// Asistencia y minuta: la minuta se envía por correo al sincronizar.
LoadData(colOutAsistencia, "rd_out_asis", true);
LoadData(colOutMinuta, "rd_out_min", true);
Set(varVerAsistencia, false);
// Última preparación guardada o descargada, y la que aún no se sube a Excel.
// Primero se define la forma de las colecciones y después se cargan las guardadas en el equipo.
ClearCollect(colPrepFila, {Clave: "", Json: "", Actualizado: "", Autor: ""});
Clear(colPrepFila);
ClearCollect(colOutPrep, {Clave: "", Json: "", Actualizado: "", Autor: ""});
Clear(colOutPrep);
LoadData(colPrepFila, "rd_prepfila", true);
LoadData(colOutPrep, "rd_out_prep", true)
