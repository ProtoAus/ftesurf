// TAS transport: fixed public origin, or a canonical loopback test listener.
string(string url) TASDirectory_Endpoint =
{
	local float n, i, c, port;
	n = strlen(url);
	if (n < 29 || n > 33) goto official;
	if (strcmp(substring(url,0,17),"http://127.0.0.1:")) goto official;
	if (strcmp(substring(url,n - 11,11),"/api/tasrev")) goto official;
	port = 0;
	for (i = 17; i < n - 11; i = i + 1)
	{
		c = str2chr(url,i);
		if (c < 48 || c > 57) goto official;
		port = port * 10 + c - 48;
	}
	if (port < 1 || port > 65535) goto official;
	return url;
:official
	return "https://play.proto.bar/api/tasrev";
};
