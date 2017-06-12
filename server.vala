/* Note: this attribute specifies the _interface_ name.  It
 * is called 'name =' for historical reasons.
 */

using Gee;


[DBus (name = "su.eerie.PhoneManager.Phone")]
public class Phone : Object {

    Array<string> ttys;
    Regex ttyregex;
    string path;
    string buspath;
    bool running;
    public string manufacturer { owned get; private set; default = "Unknown";}
    public string product { owned get; private set; default = "USB Modem";}

    public string voice_device { owned get; private set; default = "/dev/null";}
    public string data_device { owned get; private set; default = "/dev/null";}
    public string indicator_device { owned get; private set; default = "/dev/null";}

    private weak DBusConnection conn;

    public Phone(DBusConnection conn, string path, string buspath){
        this.path = path;
        this.buspath = buspath;
        this.ttyregex = new Regex ("tty[A-Z0-9]+");
        this.conn = conn;
        this.running = false;
        //this.notify.connect (send_property_change);
        this.ttys=new Array<string> ();
        load();
    }


    private void send_property_change (ParamSpec p) {
        var builder = new VariantBuilder (VariantType.ARRAY);
        var invalid_builder = new VariantBuilder (new VariantType ("as"));

        switch (p.name) {
            case "manufacturer":
                Variant i = manufacturer;
                builder.add ("{sv}", p.name, i);
                break;
            case "product":
                Variant i = product;
                builder.add ("{sv}", p.name, i);
                break;
        }

        try {
            conn.emit_signal (null,
                              buspath,
                              "org.freedesktop.DBus.Properties",
                              "PropertiesChanged",
                              new Variant ("(sa{sv}as)",
                                           "su.eerie.PhoneManager.Phone",
                                           builder,
                                           invalid_builder)
                              );
        } catch (Error e) {
            stderr.printf ("%s\n", e.message);
        }
    }


    private async void load(){
        //string[3] ttys = {"", "", ""};
        var dir = File.new_for_path (path);

        stderr.printf ("path %s\n", path);

        FindTTY(dir);

        switch(product) {
            case "HUAWEI Mobile":
                switch(ttys.length){
                  case 3:
                    voice_device=ttys.index (2);
                    data_device=ttys.index (0);
                    indicator_device=ttys.index (1);
                    break;
                  case 2:
                    data_device=ttys.index (0);
                    indicator_device=ttys.index (1);
                    break;
                }
                break;
        }

        stderr.printf ("done\n");
    }


    public async void connect_indicator() {
        if (running) {
            return ;
        }
/*
        File info = File.new_for_path (indicator_device);
        if (!info.query_exists()) {
            return ;
        }
        */

        int m_fd = Posix.open(indicator_device, flags | Posix.O_NONBLOCK);
        Posix.tcflush(m_fd, Posix.TCIOFLUSH);

        if (m_fd<0) {
                m_fd=-1;
                // TODO display error in gui
                return;
        }

        try {

        var infos = new DataInputStream (info.read ());
        infos.set_newline_type(DataStreamNewlineType.ANY);
        running = true;

        string line;
        while ((line = infos.read_line (null)) != null) {
            stdout.printf ("%s\n", line);
        }

        } catch (Error e) {
            error ("%s", e.message);
        }

        running = false;

    }


    private void FindTTY(File dir){

        Posix.Glob devices = new Posix.Glob();
        devices.glob ("%s/*/*/tty/*/dev".printf(dir.get_path () ));

        foreach (string dev in devices.pathv) {
            string[] p = dev.split("/");
            string node = "/dev/%s".printf( p[p.length -2] );
            ttys.append_val(node);

            stderr.printf ("%s\t", node);
        }


        FileEnumerator enumerator = dir.enumerate_children(
            FileAttribute.STANDARD_NAME,
            FileQueryInfoFlags.NONE
        );

        FileInfo info = null;
        while
            ((info = enumerator.next_file ()) != null)
        {
            var name = info.get_name ();
            switch (name) {
                case "manufacturer":
                    File f = dir.resolve_relative_path (info.get_name ());
                    var dis = new DataInputStream (f.read ());
                    manufacturer = dis.read_line (null);
                    break;
                case "product":
                    File f = dir.resolve_relative_path (info.get_name ());
                    var dis = new DataInputStream (f.read ());
                    product = dis.read_line (null);
                    break;
                }
/*
            if (info.get_file_type () == FileType.DIRECTORY && sub == 1 ) {
                File subdir = dir.resolve_relative_path (info.get_name ());
                File f = subdir.resolve_relative_path ("uevent");
                if ( f.query_exists () ) {

                    KeyFile uevent = new KeyFile ();
                    uevent.load_from_file(f.get_path(),KeyFileFlags.NONE);

                }
                //FindTTY(f,sub,ttys);
            }
*/
            stderr.printf ("%s\t", info.get_name ());
            stderr.printf ("%d\n", info.get_file_type ());
        }
    }

    public string reset() throws Error {

        stderr.printf ("ATZ\n");
        return "OK";

    }



}



[DBus (name = "su.eerie.PhoneManager")]
public class PhoneServer : Object {

    Regex dotregex;
    Regex nonalpharegex;

    private weak DBusConnection conn;
    private HashMap<string, Phone> map;

    public PhoneServer(DBusConnection conn) {
        this.conn = conn;
        this.map = new HashMap<string, Phone> ();

        this.dotregex = new Regex ("[.]+");
        this.nonalpharegex = new Regex ("\\W+");

    }



    public string add_by_syspath(string path, GLib.BusName sender) throws Error {
        // path = /sys/bus/usb/devices/2-2.4

        var dir = File.new_for_path (path);
        if (dir.query_exists() == false) {
            throw  new PhoneError.SOME_ERROR ("Path not exists");
        }

        var pathv = path.split("/");
        string name = pathv[pathv.length-1];

        name = dotregex.replace(name,name.length,0, "d");
        name = nonalpharegex.replace(name,name.length,0, "_");

        stderr.printf ("name %s\n", name);

        var buspath = "/su/eerie/phone/%s".printf(name);

        if (map.has_key(name)) {

        } else {

            var phone = new Phone (conn,path,buspath);
            map.set(name,phone);

            try {
                conn.register_object ("/su/eerie/phone/%s".printf(name), phone);
            } catch (IOError e) {
                stderr.printf ("Could not register service\n");
            }

        }

        return buspath;
    }
}

[DBus (name = "su.eerie.PhoneError")]
public errordomain PhoneError
{
    SOME_ERROR
}


void on_bus_aquired (DBusConnection conn) {
    try {
        conn.register_object ("/su/eerie/phone", new PhoneServer (conn));
    } catch (IOError e) {
        stderr.printf ("Could not register service\n");
    }
}

void main (string[] args) {

    Bus.own_name (BusType.SYSTEM, "su.eerie.Phone", BusNameOwnerFlags.NONE,
                  on_bus_aquired,
                  () => {},
                  () => stderr.printf ("Could not aquire name\n"));

    new MainLoop ().run ();
}
