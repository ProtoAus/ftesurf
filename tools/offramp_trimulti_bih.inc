/* PRIVATE com_bih.c include: print every BIH_TRIANGLE leaf of a BUILT model by
 * value, with its node index, in the order this walk visits the node array.
 * Setup-only, never called while PM runs; no pointer survives. Anything that
 * is not a triangle or a BIH split is counted, not skipped. The node index is
 * the same `node - cnodes` a winning trace reports as its leaf. NEVER ships.
 */
static void OfframpTriMulti_Walk(const struct bihnode_s *root, const struct bihnode_s *node, int actor, unsigned int *count, unsigned int *other)
{
	int i;
	switch (node->type)
	{
	case BIH_GROUP:
		for (i = 0; i < node->group.numchildren; i++)
			OfframpTriMulti_Walk(root, node+node->group.firstchild+i, actor, count, other);
		break;
#ifdef BIH_USEBIH
	case BIH_X:
	case BIH_Y:
	case BIH_Z:
		OfframpTriMulti_Walk(root, node+node->bihnode.firstchild+0, actor, count, other);
		OfframpTriMulti_Walk(root, node+node->bihnode.firstchild+1, actor, count, other);
		break;
#endif
	case BIH_TRIANGLE:
		Con_Printf("OFFRAMPTRIMULTI_LEAF %i %u %i %u %u %u %u", actor, *count, (int)(node-root),
			(unsigned int)node->data.tri.indexes[0], (unsigned int)node->data.tri.indexes[1],
			(unsigned int)node->data.tri.indexes[2], node->data.contents);
		for (i = 0; i < 3; i++)
		{
			const float *p = node->data.tri.xyz[node->data.tri.indexes[i]];
			Con_Printf(" %.9g %.9g %.9g", (double)p[0], (double)p[1], (double)p[2]);
		}
		Con_Printf("\n");
		(*count)++;
		break;
	default:
		(*other)++;
		break;
	}
}
void OfframpTriMulti_DumpLeaves(model_t *mod, int actor)
{
	unsigned int count = 0, other = 0;
	if (mod && mod->cnodes)
		OfframpTriMulti_Walk((const struct bihnode_s*)mod->cnodes, (const struct bihnode_s*)mod->cnodes, actor, &count, &other);
	Con_Printf("OFFRAMPTRIMULTI_LEAVES %i %u %u\n", actor, count, other);
}
