// App.OnError — en el navegador SaveData/LoadData no funcionan (solo en la app nativa).
// Se ignora ese aviso para que el prototipo se pueda probar en web; el resto de errores se muestra.
If(
    !("explorador web" in FirstError.Message || "web browser" in FirstError.Message),
    Error(FirstError)
)
