#undef PutClientInServer
void() PutClientInServer =
{
	P603_HttpRealSpawn();
	forceinfokey(self, "*phash", FS_GuidId("p603-http-synthetic-player"));
};
